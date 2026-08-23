#!/usr/bin/env python3
"""Render the multi-page GitHub Pages site from profile.yml + site.yml + publications.bib.

Single source of truth for facts is publications.bib (fact-checkable with
`aris_homepage.py check`); page structure and prose live in site.yml.

Usage:  python build.py [--out site]
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent

# --- LaTeX-ism cleanup for the handful of accents that appear in the .bib ----
LATEX_MAP = {
    r"{\'a}": "á", r"{\'e}": "é", r"{\'o}": "ó", r"{\"o}": "ö",
    r"{\'i}": "í", r"{\v s}": "š", r"\%": "%", r"\&": "&",
    "--": "–",
}


def delatex(s: str) -> str:
    for k, v in LATEX_MAP.items():
        s = s.replace(k, v)
    return s.replace("{", "").replace("}", "").strip()


# --- minimal BibTeX parser (our own well-formed file only) ------------------
ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,]+),(.*?)\n\}", re.S)
FIELD_RE = re.compile(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*(?=\n\s*\w+\s*=|\s*$)", re.S)


def parse_bib(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, dict] = {}
    for kind, key, body in ENTRY_RE.findall(text):
        fields = {k.lower(): " ".join(v.split()) for k, v in FIELD_RE.findall(body)}
        fields["_type"] = kind.lower()
        out[key.strip()] = fields
    return out


def fmt_authors(raw: str, highlight: str = "S. Pan") -> str:
    parts = [p.strip() for p in re.split(r"\s+and\s+", delatex(raw)) if p.strip()]
    names = []
    for p in parts:
        if p.lower() == "others":
            names.append("et al.")
            continue
        if "," in p:
            last, first = [x.strip() for x in p.split(",", 1)]
        else:
            bits = p.split()
            last, first = bits[-1], " ".join(bits[:-1])
        initials = " ".join(f"{b[0]}." for b in first.replace(".", " ").split() if b)
        names.append(f"{initials} {last}".strip())
    joined = ", ".join(names).replace(", et al.", " et al.")
    return joined.replace(highlight, f"<strong>{highlight}</strong>")


def fmt_venue(f: dict) -> str:
    venue = f.get("journal") or f.get("booktitle") or ""
    venue = delatex(venue)
    # the arXiv id already appears as a link — don't repeat it in the venue string
    venue = re.sub(r"\s*arXiv:\S+", "", venue).strip()
    if f.get("volume"):
        venue += f" {f['volume']}"
        if f.get("number"):
            venue += f"({f['number']})"
    if f.get("pages"):
        venue += f", {delatex(f['pages'])}"
    return venue


def pub_links(f: dict) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    if f.get("eprint"):
        links.append((f"arXiv:{f['eprint']}", f"https://arxiv.org/abs/{f['eprint']}"))
    note = f.get("note", "")
    m = re.search(r"bioRxiv\s+([\d.]+)", note)
    if m:
        links.append(("bioRxiv", f"https://www.biorxiv.org/content/10.1101/{m.group(1)}v1"))
    if f.get("doi"):
        links.append(("DOI", f"https://doi.org/{f['doi']}"))
    return links


def status_of(f: dict) -> str:
    note = f.get("note", "")
    m = re.match(r"(Under review[^;]*|Under revision[^;]*|Accepted[^;]*)", note)
    return delatex(m.group(1)) if m else ""


def render_pub(key: str, f: dict) -> str:
    title = html.escape(delatex(f.get("title", key)))
    authors = fmt_authors(f.get("author", ""))
    venue = html.escape(fmt_venue(f))
    year = f.get("year", "")
    status = html.escape(status_of(f))
    links = "".join(
        f'<a class="pub-link" href="{html.escape(u)}" target="_blank" rel="noopener">{html.escape(t)}</a>'
        for t, u in pub_links(f)
    )
    bits = [f'<div class="pub-title">{title}</div>',
            f'<div class="pub-authors">{authors}</div>']
    meta = " · ".join(x for x in [venue, year] if x)
    tail = f'<div class="pub-meta">{meta}'
    if status:
        tail += f' <span class="pub-status">{status}</span>'
    tail += f'{links}</div>'
    bits.append(tail)
    return f'<li class="pub" id="pub-{html.escape(key)}">' + "".join(bits) + "</li>"


# --- markdown-lite ----------------------------------------------------------
def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def paragraphs(text: str | None) -> str:
    if not text:
        return ""
    blocks = [b.strip() for b in text.strip().split("\n\n") if b.strip()]
    return "".join(f"<p>{inline(' '.join(b.split()))}</p>" for b in blocks)


# --- page assembly ----------------------------------------------------------
def nav_html(site: dict, current: str) -> str:
    links = "".join(
        f'<a class="{"on" if n["id"] == current else ""}" href="{n["file"]}">{html.escape(n["label"])}</a>'
        for n in site["nav"]
    )
    return f'<nav class="nav">{links}</nav>'


LINK_LABELS = [("scholar", "Google Scholar"), ("github", "GitHub"),
               ("linkedin", "LinkedIn"), ("orcid", "ORCID"), ("cv", "CV (PDF)")]


def masthead(site: dict, current: str) -> str:
    home = "" if current == "index" else '<a class="crumb" href="index.html">← Research</a>'
    parts = [f'<a href="mailto:{site["email"]}">{site["email"]}</a>']
    parts += [f'<a href="{site[k]}" target="_blank" rel="noopener">{label}</a>'
              for k, label in LINK_LABELS if site.get(k)]
    parts.append(html.escape(site["location"]))
    links = " · ".join(parts)
    return f"""<header class="masthead">
  <div class="mast-row">
    <a class="brand" href="index.html">{html.escape(site["name"])}</a>
    {home}
  </div>
  <p class="role">{inline(site["role"])}</p>
  <p class="contact">{links}</p>
</header>"""


def render_items(items: list[dict], bib: dict) -> str:
    if not items:
        return ""
    out = ['<ul class="items">']
    for it in items:
        row = [f'<div class="item-name">{inline(it["name"])}</div>']
        if it.get("detail"):
            row.append(f'<div class="item-detail">{inline(it["detail"])}</div>')
        tail = []
        if it.get("pub") and it["pub"] in bib:
            f = bib[it["pub"]]
            venue = fmt_venue(f) or f.get("year", "")
            # tags are narrow — prefer the venue's acronym when the full name carries one
            acronym = re.search(r"\(([A-Z][A-Za-z-]{1,12})\)", venue)
            if acronym:
                venue = acronym.group(1)
            tail.append(f'<a class="tag" href="#pub-{it["pub"]}">Paper · {html.escape(venue)}</a>')
        if it.get("link"):
            tail.append(f'<a class="tag" href="{it["link"]["url"]}" target="_blank" rel="noopener">{html.escape(it["link"]["label"])}</a>')
        if tail:
            row.append(f'<div class="item-tags">{"".join(tail)}</div>')
        out.append(f'<li class="item">{"".join(row)}</li>')
    out.append("</ul>")
    return "".join(out)


def render_sections(sections: list[dict], bib: dict) -> str:
    out = []
    current_part = None
    for s in sections:
        part = s.get("part")
        if part and part != current_part:
            current_part = part
            sub = f'<p class="part-sub">{inline(s["part_note"])}</p>' if s.get("part_note") else ""
            out.append(f'<div class="part"><span class="part-label">{inline(part)}</span>{sub}</div>')
        block = [f'<h2>{inline(s["title"])}</h2>']
        if s.get("meta"):
            block.append(f'<p class="sec-meta">{inline(s["meta"])}</p>')
        block.append(paragraphs(s.get("body")))
        block.append(render_items(s.get("items", []), bib))
        for key in s.get("pubs", []) or []:
            if key in bib:
                block.append(f'<ul class="pubs inline-pubs">{render_pub(key, bib[key])}</ul>')
        out.append(f'<section class="sec">{"".join(block)}</section>')
    return "".join(out)


def render_repos(repos: list[dict]) -> str:
    if not repos:
        return ""
    rows = "".join(
        f'<li class="repo"><a href="{r["url"]}" target="_blank" rel="noopener">{html.escape(r["name"])}</a>'
        f'<span class="repo-detail">{inline(r.get("detail", ""))}</span></li>'
        for r in repos
    )
    return f'<section class="sec"><h2>Code</h2><ul class="repos">{rows}</ul></section>'


def render_pubs_section(keys: list[str], bib: dict, heading: str, note: str = "") -> str:
    if not keys:
        return ""
    lis = "".join(render_pub(k, bib[k]) for k in keys if k in bib)
    n = f'<p class="sec-note">{inline(note)}</p>' if note else ""
    return f'<section class="sec"><h2>{html.escape(heading)}</h2>{n}<ul class="pubs">{lis}</ul></section>'


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="page">
{mast}
{nav}
<main>
{body}
</main>
<footer class="foot">Last updated {updated} · Built from a single CV source of truth.</footer>
</div>
</body>
</html>
"""


def build(out_dir: Path, updated: str) -> None:
    data = yaml.safe_load((ROOT / "site.yml").read_text(encoding="utf-8"))
    bib = parse_bib(ROOT / "publications.bib")
    site = data["site"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(exist_ok=True)
    (out_dir / "assets" / "style.css").write_text(CSS, encoding="utf-8")

    # --- home ---
    idx = data["index"]
    threads = "".join(
        f'<a class="thread" href="{t["page"]}.html"><span class="thread-title">{html.escape(t["title"])}</span>'
        f'<span class="thread-blurb">{inline(t["blurb"])}</span>'
        f'<span class="thread-go">Read more →</span></a>'
        for t in idx["threads"]
    )
    body = (
        f'<section class="sec lede">{paragraphs(idx["lede"])}</section>'
        f'<section class="sec"><h2>Research threads</h2><div class="threads">{threads}</div></section>'
        + render_pubs_section(idx["selected"], bib, "Selected publications", idx.get("selected_note", ""))
    )
    (out_dir / "index.html").write_text(PAGE.format(
        title=f'{site["name"]} — Research', desc=html.escape(site["role"]),
        mast=masthead(site, "index"), nav=nav_html(site, "index"),
        body=body, updated=updated), encoding="utf-8")

    # --- topic pages ---
    for pid, page in data["pages"].items():
        parts = [f'<h1 class="page-title">{html.escape(page["title"])}</h1>',
                 f'<section class="sec lede">{paragraphs(page.get("lede"))}</section>',
                 render_sections(page.get("sections", []), bib)]
        if page.get("service"):
            svc = "".join(f"<li>{inline(x)}</li>" for x in page["service"])
            parts.append(f'<section class="sec"><h2>Academic service</h2><ul class="plain">{svc}</ul></section>')
        parts.append(render_pubs_section(page.get("pubs", []), bib, "Publications"))
        parts.append(render_repos(page.get("repos", [])))
        (out_dir / f"{pid}.html").write_text(PAGE.format(
            title=f'{page["title"]} — {site["name"]}', desc=html.escape(page["title"]),
            mast=masthead(site, pid), nav=nav_html(site, pid),
            body="".join(parts), updated=updated), encoding="utf-8")

    print(f"✓ built {len(data['pages']) + 1} pages → {out_dir}")


CSS = """:root {
  --bg: #fdfdfc;
  --panel: #f5f4f1;
  --ink: #1b1a18;
  --ink-soft: #3d3b37;
  --ink-muted: #6f6b64;
  --rule: #e2dfd9;
  --accent: #8b3a2f;
  --accent-soft: #f0e6e3;
  --maxw: 780px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161513;
    --panel: #1f1e1b;
    --ink: #edeae4;
    --ink-soft: #c8c4bc;
    --ink-muted: #948f86;
    --rule: #2e2c28;
    --accent: #e08a72;
    --accent-soft: #2a211e;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial,
               "PingFang SC", "Hiragino Sans GB", sans-serif;
  font-size: 17px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: var(--maxw); margin: 0 auto; padding: 56px 24px 72px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* masthead */
.masthead { margin-bottom: 26px; }
.mast-row { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.brand {
  font-size: 30px; font-weight: 600; letter-spacing: -0.02em;
  color: var(--ink); text-decoration: none;
}
.brand:hover { text-decoration: none; color: var(--accent); }
.crumb { font-size: 14px; color: var(--ink-muted); }
.role { margin: 8px 0 4px; color: var(--ink-soft); font-size: 16px; }
.contact { margin: 0; color: var(--ink-muted); font-size: 14.5px; }

/* nav */
.nav {
  display: flex; flex-wrap: wrap; gap: 4px 18px;
  border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
  padding: 11px 0; margin-bottom: 34px;
}
.nav a { font-size: 14.5px; color: var(--ink-muted); }
.nav a.on { color: var(--ink); font-weight: 600; }
.nav a.on::before { content: "▸ "; color: var(--accent); }

/* structure */
.page-title { font-size: 27px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 4px; }
.sec { margin: 0 0 38px; }
.sec h2 {
  font-size: 15px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--ink-muted); margin: 0 0 14px; padding-bottom: 7px;
  border-bottom: 1px solid var(--rule);
}
.sec-meta { margin: -6px 0 12px; font-size: 14px; color: var(--ink-muted); }
.sec-note { margin: -6px 0 14px; font-size: 14px; color: var(--ink-muted); font-style: italic; }
.lede p { font-size: 18px; color: var(--ink-soft); }
.lede p:first-child { margin-top: 0; }
p { margin: 0 0 15px; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.9em;
  background: var(--panel); padding: 1px 5px; border-radius: 3px;
}

/* threads (home) */
.threads { display: grid; gap: 12px; }
.thread {
  display: block; padding: 16px 18px; border: 1px solid var(--rule); border-radius: 7px;
  background: var(--panel); color: var(--ink); text-decoration: none;
  transition: border-color .15s ease, transform .15s ease;
}
.thread:hover { text-decoration: none; border-color: var(--accent); transform: translateY(-1px); }
.thread-title { display: block; font-weight: 600; font-size: 17px; margin-bottom: 5px; }
.thread-blurb { display: block; color: var(--ink-soft); font-size: 15px; line-height: 1.55; }
.thread-go { display: block; margin-top: 9px; font-size: 13.5px; color: var(--accent); }

/* theory / practice part dividers */
.part { margin: 42px 0 26px; }
.part-label {
  display: inline-block; font-size: 12.5px; font-weight: 700; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--bg); background: var(--accent);
  padding: 3px 12px; border-radius: 3px;
}
.part-sub { margin: 10px 0 0; font-size: 15.5px; color: var(--ink-soft); font-style: italic; }

/* items */
.items, .pubs, .repos, .plain { list-style: none; margin: 0; padding: 0; }
.item { margin: 0 0 17px; padding-left: 15px; border-left: 2px solid var(--rule); }
.item-name { font-weight: 600; font-size: 16px; margin-bottom: 3px; }
.item-detail { color: var(--ink-soft); font-size: 15.5px; }
.item-tags { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 7px; }
.tag {
  font-size: 12.5px; padding: 2px 9px; border-radius: 20px;
  background: var(--accent-soft); color: var(--accent); border: 1px solid transparent;
}
.tag:hover { text-decoration: none; border-color: var(--accent); }

/* publications */
.pub { margin: 0 0 16px; }
.inline-pubs { margin-top: 10px; }
.pub-title { font-weight: 600; font-size: 16px; }
.pub-authors { color: var(--ink-soft); font-size: 15px; }
.pub-meta { color: var(--ink-muted); font-size: 14px; display: flex; flex-wrap: wrap; gap: 9px; align-items: baseline; }
.pub-status {
  font-size: 12px; padding: 1px 8px; border-radius: 20px;
  background: var(--accent-soft); color: var(--accent);
}
.pub-link { font-size: 13px; }

/* repos */
.repo { margin: 0 0 10px; }
.repo a { font-weight: 600; }
.repo-detail { display: block; color: var(--ink-soft); font-size: 15px; }
.plain li { margin: 0 0 7px; color: var(--ink-soft); }

.foot {
  margin-top: 46px; padding-top: 16px; border-top: 1px solid var(--rule);
  font-size: 13px; color: var(--ink-muted);
}

@media (max-width: 560px) {
  .page { padding: 36px 18px 56px; }
  .brand { font-size: 25px; }
  .lede p { font-size: 17px; }
}
"""

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    ap.add_argument("--updated", default="August 2026")
    a = ap.parse_args()
    build(ROOT / a.out, a.updated)
