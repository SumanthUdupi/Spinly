---
title: Citations
tags:
  - feature/transformer
---

Quartz uses [rehype-citation](https://github.com/timlrx/rehype-citation) to support parsing of a BibTex bibliography file.

Under the default configuration, a citation key `[@templeton2024scaling]` will be exported as `(Templeton et al., 2024)`.

> [!example]- BibTex file
>
> ```bib title="bibliography.bib"
> @article{vaswani2017attention,
>   title={Attention Is All You Need},
>   author={Vaswani, Ashish and Shazeer, Noam and Parmar, Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N. and Kaiser, Lukasz and Polosukhin, Illia},
>   year={2017},
>   journal={Advances in Neural Information Processing Systems},
>   url={https://arxiv.org/abs/1706.03762}
> }
> ```

> [!note] Behaviour of references
>
> By default, the references will be included at the end of the file. To control where the references to be included, uses `[^ref]`
>
> Refer to `rehype-citation` docs for more information.

## Customization

Citation parsing is a functionality of the [[plugins/Citations|Citation]] plugin. **This plugin is not enabled by default**. See the plugin page for customization options.
