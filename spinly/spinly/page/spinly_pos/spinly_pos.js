/**
 * Spinly POS — Staff Interface
 * State machine: Screen1 → Screen2 → Screen3 → Screen4 (Job Card)
 * All server calls via frappe.call('spinly.api.*')
 */
frappe.pages["spinly-pos"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({ parent: wrapper, title: "Spinly POS", single_column: true });

	// Inject CSS
	frappe.require("/assets/spinly/css/spinly_pos.css");

	// Inject HTML
	$(wrapper).find(".page-content").html(frappe.render_template("spinly_pos", {}));
	$(wrapper).find(".layout-main-section").css("padding", "0");
	$(wrapper).find(".container").css({ "max-width": "480px", "margin": "0 auto" });

	SpinlyPOS.init(wrapper);
};

const SpinlyPOS = (() => {
	// ── State ─────────────────────────────────────────────────────────────────
	let masters = {};
	let _searchTimer = null;
	let state = {
		phone: "",
		customer: null,          // { name, full_name, phone, tier, current_balance }
		items: {},               // { garment_type: { name, garment_name, icon_emoji, default_weight_kg, quantity } }
		service: null,
		alert_tags: new Set(),   // alert tag names
		instructions: "",
		payment_method: null,
		preview: null,           // from api.preview_order
		apply_loyalty: 0,        // points to redeem
		job_card: null,          // current job card data
	};

	const WORKFLOW_STEPS = ["Sorting", "Washing", "Drying", "Ironing", "Ready", "Delivered"];
	const WORKFLOW_ACTIONS = {
		"Sorting":  "Start Washing",
		"Washing":  "Start Drying",
		"Drying":   "Start Ironing",
		"Ironing":  "Mark Ready",
		"Ready":    "Mark Delivered",
	};

	function init(wrapper) {
		_bindKeypad();
		_bindScreen2();
		_bindScreen3();
		_bindScreen4();
		_loadMasters();
	}

	// ── Master Data ───────────────────────────────────────────────────────────
	function _loadMasters() {
		_spin(true);
		frappe.call({
			method: "spinly.api.get_pos_masters",
			callback(r) {
				_spin(false);
				if (r.message) {
					masters = r.message;
					_renderGarmentGrid();
					_renderServiceRow();
					_renderTagRow();
					_renderPaymentRow();
				}
			},
			error() {
				_spin(false);
				frappe.show_alert({ message: "Could not load POS data. Please refresh.", indicator: "red" }, 8);
			}
		});
	}

	// ── Utilities (defined before use) ───────────────────────────────────────
	// SEC-08: Only allow valid hex color codes to prevent CSS injection
	function _sanitizeColorCode(code) {
		if (!code) return null;
		const t = String(code).trim();
		return /^#[0-9A-Fa-f]{3,8}$/.test(t) ? t : null;
	}

	// ── Screen 1 — Customer Search ────────────────────────────────────────────
	function _bindKeypad() {
		document.querySelectorAll(".sp-key[data-digit]").forEach(btn => {
			btn.addEventListener("click", () => _appendDigit(btn.dataset.digit));
		});
		document.getElementById("sp-key-back").addEventListener("click", _backspace);
		document.getElementById("sp-key-clear").addEventListener("click", _clearPhone);
		document.getElementById("sp-select-customer-btn").addEventListener("click", _proceedWithCustomer);
		document.getElementById("sp-add-new-btn").addEventListener("click", _showNewCustomerForm);
		document.getElementById("sp-save-customer-btn").addEventListener("click", _saveNewCustomer);
		// Keyboard support for hardware keyboards (ignored when focus is in a text input)
		document.addEventListener("keydown", e => {
			if (!document.getElementById("sp-screen-1").classList.contains("active")) return;
			const tag = document.activeElement?.tagName;
			if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
			if (e.key >= "0" && e.key <= "9") { e.preventDefault(); _appendDigit(e.key); }
			else if (e.key === "Backspace") { e.preventDefault(); _backspace(); }
			else if (e.key === "Escape") { e.preventDefault(); _clearPhone(); }
		});
	}

	function _appendDigit(d) {
		if (state.phone.length >= 15) return;
		state.phone += d;
		_updatePhoneDisplay();
		if (state.phone.length >= 10) {
			clearTimeout(_searchTimer);
			_searchTimer = setTimeout(_searchCustomer, 300);
		}
	}
	function _backspace() {
		state.phone = state.phone.slice(0, -1);
		_updatePhoneDisplay();
		_clearCustomerResult();
	}
	function _clearPhone() {
		state.phone = "";
		_updatePhoneDisplay();
		_clearCustomerResult();
		// Re-show cursor on clear
		const cursor = document.getElementById("sp-phone-cursor");
		if (cursor) cursor.style.display = "";
	}
	function _updatePhoneDisplay() {
		const val = state.phone;
		// Format as groups of 5 for readability: 98765 43210
		let formatted = val;
		if (val.length > 5) formatted = val.slice(0, 5) + " " + val.slice(5);
		document.getElementById("sp-phone-value").textContent = formatted;
		// Show cursor only when no digits yet
		const cursor = document.getElementById("sp-phone-cursor");
		if (cursor) cursor.style.display = val.length > 0 ? "none" : "";
		// Show/hide hint
		const hint = document.querySelector(".sp-phone-hint");
		if (hint) hint.style.display = val.length > 0 ? "none" : "";
	}
	function _searchCustomer() {
		frappe.call({
			method: "spinly.api.get_customer_by_phone",
			args: { phone: state.phone },
			callback(r) {
				const cust = r.message;
				if (cust && cust.name) {
					state.customer = cust;
					_showCustomerCard(cust);
				} else {
					_clearCustomerResult();
					document.getElementById("sp-add-new-btn").classList.remove("hidden");
				}
			}
		});
	}
	function _showCustomerCard(cust) {
		const card = document.getElementById("sp-customer-card");
		document.getElementById("sp-cust-name").textContent = cust.full_name;
		document.getElementById("sp-cust-points").textContent =
			`${cust.current_balance || 0} pts`;
		document.getElementById("sp-cust-phone").textContent = cust.phone;
		const tierEl = document.getElementById("sp-cust-tier");
		_applyTierBadge(tierEl, cust.tier || "Bronze");
		card.classList.remove("hidden");
		document.getElementById("sp-select-customer-btn").classList.remove("hidden");
		document.getElementById("sp-add-new-btn").classList.add("hidden");
		document.getElementById("sp-new-customer-form").classList.add("hidden");
	}
	function _clearCustomerResult() {
		state.customer = null;
		document.getElementById("sp-customer-card").classList.add("hidden");
		document.getElementById("sp-select-customer-btn").classList.add("hidden");
		document.getElementById("sp-add-new-btn").classList.add("hidden");
	}
	function _showNewCustomerForm() {
		document.getElementById("sp-new-customer-form").classList.remove("hidden");
		document.getElementById("sp-new-name").focus();
	}
	function _saveNewCustomer() {
		const name = document.getElementById("sp-new-name").value.trim();
		if (!name) { frappe.show_alert({ message: "Enter customer name", indicator: "red" }); return; }
		_spin(true);
		frappe.call({
			method: "spinly.api.create_customer",
			args: { full_name: name, phone: state.phone },
			callback(r) {
				_spin(false);
				if (r.message) {
					state.customer = r.message;
					_showCustomerCard(r.message);
					document.getElementById("sp-new-customer-form").classList.add("hidden");
					_proceedWithCustomer();
				}
			},
			error() { _spin(false); }
		});
	}
	function _proceedWithCustomer() {
		if (!state.customer) return;
		_showScreen(2);
		_updateS2Header();
	}

	// ── Screen 2 — Order Builder ──────────────────────────────────────────────
	function _renderGarmentGrid() {
		const grid = document.getElementById("sp-garment-grid");
		grid.innerHTML = "";
		(masters.garments || []).forEach(g => {
			const btn = document.createElement("button");
			btn.className = "sp-garment-btn";
			btn.dataset.name = g.name;
			btn.dataset.defaultWeight = g.default_weight_kg || 0.3;
			btn.innerHTML = `
				<span class="sp-garment-emoji">${g.icon_emoji || "👕"}</span>
				<span class="sp-garment-name">${g.garment_name}</span>
				<div class="sp-garment-controls">
					<button class="sp-qty-btn" data-action="dec" aria-label="Decrease ${frappe.utils.escape_html(g.garment_name)} quantity">−</button>
					<span class="sp-qty-num" id="qty-${g.name}" aria-live="polite" aria-label="${frappe.utils.escape_html(g.garment_name)} quantity">0</span>
					<button class="sp-qty-btn" data-action="inc" aria-label="Increase ${frappe.utils.escape_html(g.garment_name)} quantity">+</button>
				</div>`;
			btn.querySelector("[data-action='inc']").addEventListener("click", e => {
				e.stopPropagation(); _adjustQty(g, 1);
			});
			btn.querySelector("[data-action='dec']").addEventListener("click", e => {
				e.stopPropagation(); _adjustQty(g, -1);
			});
			grid.appendChild(btn);
		});
	}

	function _adjustQty(garment, delta) {
		const cur = (state.items[garment.name]?.quantity) || 0;
		const next = Math.max(0, cur + delta);
		if (next === 0) {
			delete state.items[garment.name];
		} else {
			state.items[garment.name] = {
				garment_type: garment.name,
				garment_name: garment.garment_name,
				icon_emoji: garment.icon_emoji,
				quantity: next,
				weight_kg: garment.default_weight_kg || 0.3,
			};
		}
		document.getElementById(`qty-${garment.name}`).textContent = next;
		const btn = document.querySelector(`.sp-garment-btn[data-name="${garment.name}"]`);
		btn.classList.toggle("selected", next > 0);
		_updateOrderSummary();
	}

	function _renderServiceRow() {
		const row = document.getElementById("sp-service-row");
		row.innerHTML = "";
		(masters.services || []).forEach((s, i) => {
			const btn = document.createElement("button");
			btn.className = "sp-service-btn";
			btn.dataset.name = s.name;
			const sym = masters.currency_symbol || "₹";
			btn.innerHTML = `
				<span class="sp-service-name">${s.service_name}</span>
				<span class="sp-service-price">${sym}${s.base_price_per_kg}/kg</span>`;
			btn.addEventListener("click", () => {
				state.service = s.name;
				document.querySelectorAll(".sp-service-btn").forEach(b => b.classList.remove("selected"));
				btn.classList.add("selected");
				_updateOrderSummary();
			});
			row.appendChild(btn);
			if (i === 0) { state.service = s.name; btn.classList.add("selected"); }
		});
	}

	function _renderTagRow() {
		const row = document.getElementById("sp-tag-row");
		row.innerHTML = "";
		(masters.alert_tags || []).forEach(tag => {
			const btn = document.createElement("button");
			btn.className = "sp-tag-btn";
			btn.dataset.name = tag.name;
			btn.textContent = `${tag.icon_emoji || ""} ${tag.tag_name}`.trim();
			const tagColor = _sanitizeColorCode(tag.color_code) || "#ef4444";
			btn.style.setProperty("--tag-color", tagColor);
			btn.addEventListener("click", () => {
				if (state.alert_tags.has(tag.name)) {
					state.alert_tags.delete(tag.name);
					btn.classList.remove("selected");
					btn.style.background = "";
					btn.style.borderColor = "";
				} else {
					state.alert_tags.add(tag.name);
					btn.classList.add("selected");
					btn.style.background = tagColor + "33";
					btn.style.borderColor = tagColor;
				}
			});
			row.appendChild(btn);
		});
	}

	function _renderPaymentRow() {
		const row = document.getElementById("sp-payment-row");
		row.innerHTML = "";
		(masters.payment_methods || []).forEach((pm, i) => {
			const btn = document.createElement("button");
			btn.className = "sp-payment-btn";
			btn.dataset.name = pm.name;
			btn.textContent = pm.method_name;
			btn.addEventListener("click", () => {
				state.payment_method = pm.name;
				document.querySelectorAll(".sp-payment-btn").forEach(b => b.classList.remove("selected"));
				btn.classList.add("selected");
			});
			row.appendChild(btn);
			if (i === 0) { state.payment_method = pm.name; btn.classList.add("selected"); }
		});
	}

	function _updateOrderSummary() {
		const sym = masters.currency_symbol || "₹";
		let totalWeight = 0, totalPrice = 0;
		const service = (masters.services || []).find(s => s.name === state.service);
		const pricePerKg = service?.base_price_per_kg || 0;
		Object.values(state.items).forEach(row => {
			totalWeight += (row.weight_kg || 0) * (row.quantity || 0);
			totalPrice  += (row.weight_kg || 0) * (row.quantity || 0) * pricePerKg;
		});
		document.getElementById("sp-weight-display").textContent = `${totalWeight.toFixed(2)} kg`;
		document.getElementById("sp-price-display").textContent = `${sym}${totalPrice.toFixed(2)}`;
		const hasItems = Object.keys(state.items).length > 0;
		const reviewBtn = document.getElementById("sp-review-btn");
		reviewBtn.disabled = !hasItems;
		const helper = document.getElementById("sp-review-helper");
		if (helper) helper.style.display = hasItems ? "none" : "";
	}

	function _bindScreen2() {
		document.getElementById("sp-s2-back").addEventListener("click", () => _showScreen(1));
		document.getElementById("sp-review-btn").addEventListener("click", _previewOrder);
	}
	function _updateS2Header() {
		const cust = state.customer;
		if (!cust) return;
		document.getElementById("sp-s2-customer-name").textContent = cust.full_name;
		const tierEl = document.getElementById("sp-s2-tier");
		_applyTierBadge(tierEl, cust.tier || "Bronze");
	}

	// ── Screen 3 — Confirm ────────────────────────────────────────────────────
	function _previewOrder() {
		const items = Object.values(state.items);
		if (!items.length) return;
		_spin(true);
		frappe.call({
			method: "spinly.api.preview_order",
			args: {
				customer: state.customer.name,
				service: state.service,
				items: JSON.stringify(items),
				alert_tag_names: JSON.stringify([...state.alert_tags]),
			},
			callback(r) {
				_spin(false);
				if (r.message) {
					state.preview = r.message;
					state.apply_loyalty = 0;
					_renderScreen3();
					_showScreen(3);
				}
			},
			error() { _spin(false); }
		});
	}

	function _renderScreen3() {
		const p = state.preview;
		const sym = masters.currency_symbol || "₹";
		// Machine + ETA
		const machineName = p.assigned_machine
			? (masters.machines?.find(m => m.name === p.assigned_machine)?.machine_name || p.assigned_machine)
			: "Auto-assigned";
		document.getElementById("sp-confirm-machine").textContent = machineName;
		document.getElementById("sp-confirm-eta").textContent = p.expected_ready_date
			? frappe.datetime.str_to_user(p.expected_ready_date) : "TBD";

		// Alert tags
		const tagsEl = document.getElementById("sp-confirm-tags");
		tagsEl.innerHTML = "";
		[...state.alert_tags].forEach(tagName => {
			const tag = (masters.alert_tags || []).find(t => t.name === tagName);
			if (!tag) return;
			const span = document.createElement("span");
			span.className = "sp-confirm-tag";
			const tagColor = _sanitizeColorCode(tag.color_code) || "#ef4444";
			span.style.background = tagColor + "33";
			span.style.border = `2px solid ${tagColor}`;
			span.style.color = tagColor;
			span.textContent = `${tag.icon_emoji || "⚠️"} ${tag.tag_name}`;
			tagsEl.appendChild(span);
		});

		// Loyalty prompt
		const loyaltyBalance = p.loyalty_balance || 0;
		const loyaltyPrompt = document.getElementById("sp-loyalty-prompt");
		if (loyaltyBalance > 0) {
			document.getElementById("sp-loyalty-text").textContent =
				`Apply ${loyaltyBalance} pts for ${sym}${loyaltyBalance} off?`;
			loyaltyPrompt.classList.remove("hidden");
		} else {
			loyaltyPrompt.classList.add("hidden");
		}

		// Prices
		_updateScreen3Prices();
	}

	function _updateScreen3Prices() {
		const p = state.preview;
		const sym = masters.currency_symbol || "₹";
		const discount = state.apply_loyalty || 0;
		const grandTotal = Math.max(0, (p.grand_total || 0) - discount);
		document.getElementById("sp-sub-display").textContent = `${sym}${(p.subtotal || 0).toFixed(2)}`;
		const discRow = document.getElementById("sp-discount-row");
		if (discount > 0) {
			discRow.style.display = "";
			document.getElementById("sp-discount-display").textContent = `−${sym}${discount.toFixed(0)}`;
		} else {
			discRow.style.display = "none";
		}
		document.getElementById("sp-total-display").textContent = `${sym}${grandTotal.toFixed(2)}`;
	}

	function _bindScreen3() {
		document.getElementById("sp-s3-back").addEventListener("click", () => _showScreen(2));
		document.getElementById("sp-loyalty-yes").addEventListener("click", () => {
			state.apply_loyalty = state.preview?.loyalty_balance || 0;
			document.getElementById("sp-loyalty-prompt").classList.add("hidden");
			_updateScreen3Prices();
		});
		document.getElementById("sp-loyalty-no").addEventListener("click", () => {
			state.apply_loyalty = 0;
			document.getElementById("sp-loyalty-prompt").classList.add("hidden");
			_updateScreen3Prices();
		});
		document.getElementById("sp-confirm-btn").addEventListener("click", _submitOrder);
	}

	function _submitOrder() {
		if (!state.customer) return;
		const confirmBtn = document.getElementById("sp-confirm-btn");
		if (confirmBtn) confirmBtn.disabled = true;
		_spin(true);
		const items = Object.values(state.items);
		frappe.call({
			method: "spinly.api.submit_order",
			args: {
				customer: state.customer.name,
				service: state.service,
				items: JSON.stringify(items),
				alert_tag_names: JSON.stringify([...state.alert_tags]),
				payment_method: state.payment_method,
				apply_loyalty_points: state.apply_loyalty,
				special_instructions: document.getElementById("sp-instructions")?.value || "",
			},
			callback(r) {
				_spin(false);
				if (confirmBtn) confirmBtn.disabled = false;
				if (r.message) {
					const result = r.message;
					frappe.show_alert({ message: `Order ${result.order} created!`, indicator: "green" });
					// Trigger prints
					_printJobTag(result.order);
					_printInvoice(result.order);
					// Load job card screen
					if (result.job_card) {
						// Brief success flash on confirm button before transitioning
						const btn = document.getElementById("sp-confirm-btn");
						if (btn) btn.classList.add("sp-success-flash");
						setTimeout(() => {
							if (btn) btn.classList.remove("sp-success-flash");
							_loadJobCard(result.job_card);
						}, 350);
					} else {
						frappe.show_alert({
							message: `Order ${result.order} created — no job card found. Search orders to continue.`,
							indicator: "orange"
						}, 8);
					}
				}
			},
			error() {
				_spin(false);
				if (confirmBtn) confirmBtn.disabled = false;
			}
		});
	}

	// ── Screen 4 — Job Card Advancement ──────────────────────────────────────
	function _loadJobCard(jcName) {
		_spin(true);
		frappe.call({
			method: "spinly.api.get_job_card",
			args: { job_card: jcName },
			callback(r) {
				_spin(false);
				if (r.message) {
					state.job_card = r.message;
					_renderScreen4(r.message);
					_showScreen(4);
				}
			},
			error() { _spin(false); }
		});
	}

	function _renderScreen4(jc) {
		document.getElementById("sp-s4-order-id").textContent = jc.laundry_order || "";
		document.getElementById("sp-lot-display").textContent = jc.lot_number || "–";
		document.getElementById("sp-machine-display").textContent =
			jc.machine_name ? `${jc.machine_name} (${jc.assigned_machine})` : "No machine assigned";

		const tierEl = document.getElementById("sp-s4-tier");
		_applyTierBadge(tierEl, jc.customer_tier_badge || "Bronze");

		// Alert tags
		const tagsEl = document.getElementById("sp-s4-tags");
		tagsEl.innerHTML = "";
		(jc.alert_tags || []).forEach(tag => {
			const span = document.createElement("span");
			span.className = "sp-confirm-tag";
			const tagColor = _sanitizeColorCode(tag.color_code) || "#ef4444";
			span.style.background = tagColor + "33";
			span.style.border = `2px solid ${tagColor}`;
			span.style.color = tagColor;
			span.textContent = `${tag.icon_emoji || "⚠️"} ${tag.tag_name}`;
			tagsEl.appendChild(span);
		});

		// Special instructions
		const instrEl = document.getElementById("sp-s4-instructions");
		if (jc.special_instructions) {
			instrEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="vertical-align:middle;margin-right:5px"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>${frappe.utils.escape_html(jc.special_instructions)}`;
			instrEl.classList.remove("hidden");
		}

		// Workflow progress
		const currentState = jc.workflow_state || "Sorting";
		_renderWorkflowBar(currentState);

		// Buttons
		_updateJobCardButtons(currentState, jc.payment_status);
	}

	function _renderWorkflowBar(currentState) {
		const stepsEl = document.getElementById("sp-wf-steps");
		stepsEl.innerHTML = "";
		const currentIdx = WORKFLOW_STEPS.indexOf(currentState);
		WORKFLOW_STEPS.forEach((step, i) => {
			const stepEl = document.createElement("div");
			stepEl.className = "sp-wf-step";
			const dot = document.createElement("div");
			dot.className = "sp-wf-dot";
			const label = document.createElement("div");
			label.className = "sp-wf-label";
			label.textContent = step;
			if (i < currentIdx) { stepEl.classList.add("done"); dot.classList.add("done"); label.classList.add("done"); }
			else if (i === currentIdx) { dot.classList.add("active"); label.classList.add("active"); }
			stepEl.appendChild(dot);
			stepEl.appendChild(label);
			stepsEl.appendChild(stepEl);
		});
		const stateLabel = document.getElementById("sp-current-state");
		stateLabel.textContent = currentState;
		stateLabel.className = "sp-state-label" + (currentState === "Delivered" ? " done" : "");
	}

	function _updateJobCardButtons(currentState, paymentStatus) {
		const nextBtn = document.getElementById("sp-next-step-btn");
		const paidBtn = document.getElementById("sp-mark-paid-btn");
		const action = WORKFLOW_ACTIONS[currentState];

		if (!action) {
			nextBtn.classList.add("hidden");
		} else {
			nextBtn.classList.remove("hidden");
			if (currentState === "Ready") {
				nextBtn.className = "sp-btn sp-btn-green sp-btn-full sp-btn-xl";
				nextBtn.innerHTML = `MARK AS DELIVERED
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;flex-shrink:0">
						<polyline points="20 6 9 17 4 12"/>
					</svg>`;
			} else {
				nextBtn.className = "sp-btn sp-btn-orange sp-btn-full sp-btn-xl";
				nextBtn.innerHTML = `NEXT STEP
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:20px;height:20px;flex-shrink:0">
						<polyline points="9 18 15 12 9 6"/>
					</svg>`;
			}
		}

		// Show MARK AS PAID when Ready or Delivered and not yet paid
		if ((currentState === "Ready" || currentState === "Delivered") && paymentStatus !== "Paid") {
			paidBtn.classList.remove("hidden");
		} else {
			paidBtn.classList.add("hidden");
		}
	}

	function _bindScreen4() {
		document.getElementById("sp-s4-back").addEventListener("click", _resetToScreen1);
		document.getElementById("sp-next-step-btn").addEventListener("click", _advanceJobCard);
		document.getElementById("sp-mark-paid-btn").addEventListener("click", _markPaid);
	}

	function _advanceJobCard() {
		const jc = state.job_card;
		if (!jc) return;
		const action = WORKFLOW_ACTIONS[jc.workflow_state];
		if (!action) return;
		_spin(true);
		frappe.call({
			method: "spinly.api.advance_job_card",
			args: { job_card: jc.name, action },
			callback(r) {
				_spin(false);
				if (r.message) {
					const newState = r.message.workflow_state;
					state.job_card.workflow_state = newState;
					_renderWorkflowBar(newState);
					_updateJobCardButtons(newState, jc.payment_status);
					frappe.show_alert({ message: `→ ${newState}`, indicator: "green" });
				}
			},
			error() { _spin(false); }
		});
	}

	function _markPaid() {
		const jc = state.job_card;
		if (!jc) return;
		_spin(true);
		frappe.call({
			method: "spinly.api.mark_order_paid",
			args: { order_name: jc.laundry_order, payment_method: state.payment_method || "" },
			callback(r) {
				_spin(false);
				if (r.message) {
					state.job_card.payment_status = "Paid";
					document.getElementById("sp-mark-paid-btn").classList.add("hidden");
					frappe.show_alert({ message: "Payment recorded ✅", indicator: "green" });
				}
			},
			error() { _spin(false); }
		});
	}

	// ── Print ─────────────────────────────────────────────────────────────────
	function _printJobTag(orderName) {
		const url = frappe.urllib.get_full_url(
			`/api/method/frappe.utils.print_format.download_pdf?doctype=Laundry+Order&name=${encodeURIComponent(orderName)}&format=Job+Tag+Thermal&no_letterhead=1`
		);
		window.open(url, "_blank");
	}
	function _printInvoice(orderName) {
		const url = frappe.urllib.get_full_url(
			`/api/method/frappe.utils.print_format.download_pdf?doctype=Laundry+Order&name=${encodeURIComponent(orderName)}&format=Customer+Invoice`
		);
		window.open(url, "_blank");
	}

	// ── Utilities ─────────────────────────────────────────────────────────────
	function _showScreen(n) {
		[1, 2, 3, 4].forEach(i => {
			const el = document.getElementById(`sp-screen-${i}`);
			if (el) { el.classList.toggle("active", i === n); el.classList.toggle("hidden", i !== n); }
		});
	}

	function _resetToScreen1() {
		state.phone = "";
		state.customer = null;
		state.items = {};
		state.service = null;
		state.alert_tags = new Set();
		state.instructions = "";
		state.payment_method = null;
		state.preview = null;
		state.apply_loyalty = 0;
		state.job_card = null;
		// Reset UI
		document.getElementById("sp-phone-value").textContent = "";
		const cursor = document.getElementById("sp-phone-cursor");
		if (cursor) cursor.style.display = "";
		const hint = document.querySelector(".sp-phone-hint");
		if (hint) hint.style.display = "";
		document.getElementById("sp-customer-card").classList.add("hidden");
		document.getElementById("sp-select-customer-btn").classList.add("hidden");
		document.getElementById("sp-add-new-btn").classList.add("hidden");
		document.getElementById("sp-new-customer-form").classList.add("hidden");
		// Reset qty counters
		document.querySelectorAll(".sp-qty-num").forEach(el => el.textContent = "0");
		document.querySelectorAll(".sp-garment-btn").forEach(el => el.classList.remove("selected"));
		_renderPaymentRow();
		_showScreen(1);
	}

	function _applyTierBadge(el, tier) {
		const clsMap = {
			Bronze: "sp-tier-bronze", Silver: "sp-tier-silver", Gold: "sp-tier-gold", Diamond: "sp-tier-diamond"
		};
		el.textContent = tier || "Bronze";
		el.className = el.className.replace(/\bsp-tier-\w+/g, "");
		el.classList.add("sp-tier-badge", clsMap[tier] || "sp-tier-bronze");
	}

	function _spin(on) {
		document.getElementById("sp-spinner").classList.toggle("hidden", !on);
	}

	return { init };
})();
