# Manuscript experiments

Scripts and data behind Sections 6 and 7 of the manuscript *Volcano Compressibility Agent: coupling an AI
literature agent to a magma-compressibility model of volcanic ground deformation* (Freya Mohammadian, in
preparation). No API key is needed: every experiment runs the deterministic engine on the La Fossa
reference dataset (`volcano_agent/reference/lafossa.json`).

```bash
pip install -r requirements.txt
python paper/experiments.py     # ≈ 2 min; writes paper/results.json
python paper/figures.py         # writes Figures 1–4 as PNG (300 dpi) and PDF
```

Set `VOLCANO_AGENT_EVO_DIR=/path/to/EVo` to reuse an existing EVo checkout; otherwise EVo is cloned at the
pinned commit on first use.

| File | Content |
|---|---|
| `experiments.py` | (0) regression of the engine against the 13 thesis configurations and timing; (1) value of the literature data: inputs replaced by generic defaults in three nested steps; (2) twelve injected extraction errors, each compared with the baseline configuration by configuration; (3) summary of the edge-case test datasets |
| `results.json` | output of `experiments.py` as used in the manuscript |
| `figures.py` | Figure 1 (volume partitioning above the 2021 La Fossa source, 3-D surfaces computed with the engine), Figure 2 (architecture), Figure 3 (regression against the thesis), Figure 4 (value of literature data); palette lava / indigo / teal, checked for colour-vision deficiency |

Section 8 of the manuscript (evaluation of the research agent on real volcanoes) is a protocol; its runs need an
API key and are not part of this folder yet.
