# runningstone.github.io

Personal academic homepage for Shi Pan. Static, no build dependencies beyond `pyyaml`.

## Structure

| Path | Role |
|---|---|
| `publications.bib` | **Single source of truth for publication facts.** Fact-checkable against DBLP / arXiv. |
| `profile.yml` | Identity, affiliations, education, links. |
| `site.yml` | Page structure and prose for all four pages. |
| `build.py` | Renderer: `site.yml` + `publications.bib` → `docs/*.html` + `docs/assets/style.css`. |
| `docs/` | **Published output.** GitHub Pages serves this directory. Do not hand-edit. |

## Pages

- `index.html` — research statement + selected publications
- `agent.html` — Agents & Post-Training (organised around the evaluation-to-training loop)
- `multimodal.html` — Multimodal & Virtual Cell
- `systems.html` — Systems & Earlier Work

## Rebuild

```bash
python3 -m venv .venv && .venv/bin/pip install pyyaml
.venv/bin/python build.py --out docs --updated "August 2026"
```

Edit `site.yml` (prose, sections) or `publications.bib` (papers), then rebuild and commit `docs/`.

## Fact-checking publications

The bib file is compatible with the ARIS homepage auditor:

```bash
aris_homepage.py check
```

Venue-name mismatches against DBLP (`CoRR` vs `arXiv preprint`, `CVPR Workshops` vs the full
name) are expected and intentional. Biology/medicine journals are not indexed by DBLP, so
`no_dblp_hit` warnings for those entries are also expected.
