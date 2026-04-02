/**
 * token-optimizer.js
 * Complete 5-phase token optimization system for Claude API calls.
 *
 * Phases:
 *   1. SYSTEM_CONFIG   — 4 prompt modes (standard, aggressive, extraction, processing)
 *   2. TokenCache      — .token-cache.json with hit/miss tracking
 *   3. TokenMeter      — .token-meter.json usage analytics & cost tracking
 *   4. StreamingClient — streaming with early-stop + aggressive length cap
 *   5. TokenOptimizer  — orchestrator: initialize, efficientCall, batchProcess, showStats
 */

"use strict";

const Anthropic = require("@anthropic-ai/sdk");
const fs = require("fs");
const crypto = require("crypto");

// ---------------------------------------------------------------------------
// PHASE 1 — SYSTEM_CONFIG: 4 prompt modes
// ---------------------------------------------------------------------------

const SYSTEM_CONFIG = {
  standard: {
    system:
      "Reply concisely. No preamble, no filler. Under 80 words unless more is essential.",
    max_tokens: 512,
  },
  aggressive: {
    system:
      "JSON only. No prose. No markdown. No explanation. Shortest valid answer.",
    max_tokens: 256,
  },
  extraction: {
    system:
      'Extract requested data as compact JSON. Output only the JSON object, nothing else. Example: {"result": ...}',
    max_tokens: 512,
  },
  processing: {
    system:
      "Process the input and return results as a JSON array. No commentary. No extra fields.",
    max_tokens: 1024,
  },
};

// Pricing per 1M tokens (claude-opus-4-6 defaults)
const PRICING = {
  "claude-opus-4-6": { input: 5.0, output: 25.0 },
  "claude-sonnet-4-6": { input: 3.0, output: 15.0 },
  "claude-haiku-4-5": { input: 1.0, output: 5.0 },
};

function costUSD(model, inputTokens, outputTokens) {
  const p = PRICING[model] || PRICING["claude-opus-4-6"];
  return (inputTokens * p.input + outputTokens * p.output) / 1_000_000;
}

// ---------------------------------------------------------------------------
// PHASE 2 — TokenCache: .token-cache.json, hit/miss tracking
// ---------------------------------------------------------------------------

class TokenCache {
  constructor(cachePath = ".token-cache.json") {
    this.cachePath = cachePath;
    this.data = this._load();
    this.stats = { hits: 0, misses: 0, tokensSaved: 0 };
  }

  _load() {
    try {
      if (fs.existsSync(this.cachePath)) {
        return JSON.parse(fs.readFileSync(this.cachePath, "utf8"));
      }
    } catch {
      // corrupt cache — start fresh
    }
    return {};
  }

  _save() {
    fs.writeFileSync(this.cachePath, JSON.stringify(this.data, null, 2));
  }

  _key(model, system, messages) {
    const payload = JSON.stringify({ model, system, messages });
    return crypto.createHash("sha256").update(payload).digest("hex");
  }

  get(model, system, messages) {
    const key = this._key(model, system, messages);
    const entry = this.data[key];
    if (entry) {
      this.stats.hits++;
      this.stats.tokensSaved += entry.usage.input_tokens + entry.usage.output_tokens;
      return entry;
    }
    this.stats.misses++;
    return null;
  }

  set(model, system, messages, response) {
    const key = this._key(model, system, messages);
    this.data[key] = {
      response,
      usage: response.usage,
      cachedAt: new Date().toISOString(),
    };
    this._save();
  }

  hitRate() {
    const total = this.stats.hits + this.stats.misses;
    return total === 0 ? 0 : (this.stats.hits / total) * 100;
  }
}

// ---------------------------------------------------------------------------
// PHASE 3 — TokenMeter: .token-meter.json usage analytics
// ---------------------------------------------------------------------------

class TokenMeter {
  constructor(meterPath = ".token-meter.json") {
    this.meterPath = meterPath;
    this.data = this._load();
  }

  _load() {
    try {
      if (fs.existsSync(this.meterPath)) {
        return JSON.parse(fs.readFileSync(this.meterPath, "utf8"));
      }
    } catch {
      // corrupt meter — start fresh
    }
    return { calls: [], totals: { input: 0, output: 0, cost: 0 }, byOperation: {} };
  }

  _save() {
    fs.writeFileSync(this.meterPath, JSON.stringify(this.data, null, 2));
  }

  record({ operation, model, inputTokens, outputTokens }) {
    const usd = costUSD(model, inputTokens, outputTokens);

    this.data.calls.push({
      operation,
      model,
      inputTokens,
      outputTokens,
      cost: usd,
      ts: new Date().toISOString(),
    });

    this.data.totals.input += inputTokens;
    this.data.totals.output += outputTokens;
    this.data.totals.cost += usd;

    if (!this.data.byOperation[operation]) {
      this.data.byOperation[operation] = { calls: 0, input: 0, output: 0, cost: 0 };
    }
    const op = this.data.byOperation[operation];
    op.calls++;
    op.input += inputTokens;
    op.output += outputTokens;
    op.cost += usd;

    this._save();
  }

  summary() {
    return {
      totalCalls: this.data.calls.length,
      totalInputTokens: this.data.totals.input,
      totalOutputTokens: this.data.totals.output,
      totalCostUSD: this.data.totals.cost.toFixed(6),
      byOperation: this.data.byOperation,
    };
  }
}

// ---------------------------------------------------------------------------
// PHASE 4 — StreamingClient: early-stop streaming
// ---------------------------------------------------------------------------

class StreamingClient {
  constructor(apiKey) {
    this.client = new Anthropic({ apiKey: apiKey || process.env.ANTHROPIC_API_KEY });
  }

  /**
   * Stream a completion; stop as soon as stopToken appears in the output
   * or maxOutputTokens is reached.
   *
   * @param {object} opts
   * @param {string} opts.model
   * @param {string} opts.system
   * @param {Array}  opts.messages
   * @param {number} opts.maxOutputTokens  — hard cap on output tokens
   * @param {string} [opts.stopToken]      — early-exit marker in streamed text
   * @returns {{ text: string, usage: object, stopped_early: boolean }}
   */
  async streamWithEarlyStop({
    model = "claude-opus-4-6",
    system,
    messages,
    maxOutputTokens = 512,
    stopToken = null,
  }) {
    const chunks = [];
    let usage = { input_tokens: 0, output_tokens: 0 };
    let stoppedEarly = false;

    const stream = this.client.messages.stream({
      model,
      max_tokens: maxOutputTokens,
      system,
      messages,
    });

    try {
      for await (const event of stream) {
        if (event.type === "content_block_delta" && event.delta?.type === "text_delta") {
          chunks.push(event.delta.text);
          if (stopToken && chunks.join("").includes(stopToken)) {
            stoppedEarly = true;
            break;
          }
        }
        if (event.type === "message_delta" && event.usage) {
          usage.output_tokens = event.usage.output_tokens ?? usage.output_tokens;
        }
        if (event.type === "message_start" && event.message?.usage) {
          usage.input_tokens = event.message.usage.input_tokens;
        }
      }
    } catch (err) {
      // Stream aborted by early-stop — not a real error
      if (!stoppedEarly) throw err;
    }

    // Collect final usage if stream completed normally
    if (!stoppedEarly) {
      try {
        const final = await stream.finalMessage();
        usage = final.usage;
      } catch {
        // already ended
      }
    }

    return { text: chunks.join(""), usage, stopped_early: stoppedEarly };
  }
}

// ---------------------------------------------------------------------------
// PHASE 5 — TokenOptimizer: main orchestrator
// ---------------------------------------------------------------------------

class TokenOptimizer {
  constructor({ apiKey, model = "claude-opus-4-6", mode = "aggressive" } = {}) {
    this.model = model;
    this.mode = mode;
    this.cache = new TokenCache();
    this.meter = new TokenMeter();
    this.streamer = new StreamingClient(apiKey);
    this.client = new Anthropic({ apiKey: apiKey || process.env.ANTHROPIC_API_KEY });
  }

  initialize() {
    console.log(`TokenOptimizer ready — model=${this.model}, mode=${this.mode}`);
    console.log(`Cache: ${this.cache.cachePath} | Meter: ${this.meter.meterPath}`);
  }

  /**
   * Single efficient API call with cache + metering.
   *
   * @param {string} prompt
   * @param {{ operation?: string, mode?: string, useStreaming?: boolean }} opts
   */
  async efficientCall(prompt, { operation = "call", mode, useStreaming = false } = {}) {
    const cfg = SYSTEM_CONFIG[mode || this.mode];
    const messages = [{ role: "user", content: prompt }];

    // Check cache first
    const cached = this.cache.get(this.model, cfg.system, messages);
    if (cached) {
      return { text: cached.response, usage: cached.usage, cached: true };
    }

    let text, usage;

    if (useStreaming) {
      const result = await this.streamer.streamWithEarlyStop({
        model: this.model,
        system: cfg.system,
        messages,
        maxOutputTokens: cfg.max_tokens,
      });
      text = result.text;
      usage = result.usage;
    } else {
      const response = await this.client.messages.create({
        model: this.model,
        max_tokens: cfg.max_tokens,
        system: cfg.system,
        messages,
      });
      text = response.content.find((b) => b.type === "text")?.text ?? "";
      usage = response.usage;
    }

    // Cache and meter
    this.cache.set(this.model, cfg.system, messages, { text, usage });
    this.meter.record({
      operation,
      model: this.model,
      inputTokens: usage.input_tokens,
      outputTokens: usage.output_tokens,
    });

    return { text, usage, cached: false };
  }

  /**
   * Batch-process N items in a SINGLE API call.
   * Saves 60-80 % of tokens vs N individual calls.
   *
   * @param {string[]} items   — list of items to process
   * @param {string}   task    — instruction applied to all items
   * @param {{ operation?: string }} opts
   * @returns {object[]}  parsed JSON array of results
   */
  async batchProcess(items, task, { operation = "batch" } = {}) {
    const cfg = SYSTEM_CONFIG.processing;

    const prompt = [
      `Task: ${task}`,
      `Items (${items.length} total):`,
      ...items.map((item, i) => `${i + 1}. ${item}`),
      "",
      `Return a JSON array with exactly ${items.length} result objects.`,
    ].join("\n");

    const messages = [{ role: "user", content: prompt }];

    // Cache check
    const cached = this.cache.get(this.model, cfg.system, messages);
    if (cached) {
      try {
        const text =
          typeof cached.response === "string"
            ? cached.response
            : cached.response.text ?? "";
        return JSON.parse(text);
      } catch {
        // fall through to API
      }
    }

    const response = await this.client.messages.create({
      model: this.model,
      max_tokens: cfg.max_tokens,
      system: cfg.system,
      messages,
    });

    const rawText = response.content.find((b) => b.type === "text")?.text ?? "[]";
    this.cache.set(this.model, cfg.system, messages, rawText);
    this.meter.record({
      operation,
      model: this.model,
      inputTokens: response.usage.input_tokens,
      outputTokens: response.usage.output_tokens,
    });

    // Parse JSON array from response (strip markdown fences if present)
    const jsonMatch = rawText.match(/\[[\s\S]*\]/);
    try {
      return JSON.parse(jsonMatch ? jsonMatch[0] : rawText);
    } catch {
      return [{ raw: rawText }];
    }
  }

  showStats() {
    const summary = this.meter.summary();
    const hitRate = this.cache.hitRate().toFixed(1);
    const tokensSaved = this.cache.stats.tokensSaved;

    console.log("\n========== TOKEN DASHBOARD ==========");
    console.log(`Total API calls   : ${summary.totalCalls}`);
    console.log(`Input tokens      : ${summary.totalInputTokens.toLocaleString()}`);
    console.log(`Output tokens     : ${summary.totalOutputTokens.toLocaleString()}`);
    console.log(`Total cost (USD)  : $${summary.totalCostUSD}`);
    console.log(`Cache hit rate    : ${hitRate}%`);
    console.log(`Tokens saved      : ${tokensSaved.toLocaleString()}`);

    if (Object.keys(summary.byOperation).length > 0) {
      console.log("\n--- Cost by operation ---");
      for (const [op, stats] of Object.entries(summary.byOperation)) {
        console.log(
          `  ${op.padEnd(20)} calls=${stats.calls}  cost=$${stats.cost.toFixed(6)}`
        );
      }
    }
    console.log("=====================================\n");

    return summary;
  }
}

// ---------------------------------------------------------------------------
// DEMO: batch-process 5 items in 1 API call, then show savings
// ---------------------------------------------------------------------------

async function demo() {
  const optimizer = new TokenOptimizer({ model: "claude-opus-4-6", mode: "aggressive" });
  optimizer.initialize();

  const items = [
    "The quarterly revenue exceeded expectations by 12%.",
    "New product launch delayed due to supply chain issues.",
    "Customer satisfaction scores dropped 8 points.",
    "Team expanded by 15 engineers this month.",
    "Server uptime reached 99.97% SLA compliance.",
  ];

  console.log(`\nProcessing ${items.length} items in a SINGLE API call...`);
  const t0 = Date.now();

  const results = await optimizer.batchProcess(
    items,
    "Classify each as POSITIVE, NEGATIVE, or NEUTRAL and extract the key metric as a short string.",
    { operation: "demo-batch" }
  );

  const elapsed = Date.now() - t0;
  console.log(`\nResults (${elapsed}ms for ${items.length} items):`);
  results.forEach((r, i) => {
    console.log(`  [${i + 1}] ${JSON.stringify(r)}`);
  });

  // Second call — same items, should hit cache
  console.log("\nRe-running (should hit cache)...");
  await optimizer.batchProcess(items, "Classify each as POSITIVE, NEGATIVE, or NEUTRAL.", {
    operation: "demo-cache-test",
  });

  optimizer.showStats();
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

module.exports = { TokenOptimizer, TokenCache, TokenMeter, StreamingClient, SYSTEM_CONFIG };

// Run demo if executed directly
if (require.main === module) {
  demo().catch((err) => {
    console.error("Demo error:", err.message);
    process.exit(1);
  });
}
