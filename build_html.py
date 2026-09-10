#!/usr/bin/env python3
"""Convert the OSI README.md files to standalone styled HTML.

Handles the markdown subset actually used in those documents:
headings, tables, fenced code, blockquotes, flat ul/ol lists,
horizontal rules, and inline bold / code / links / images.
"""
import html
import re
import sys
from pathlib import Path

# ---------- inline ----------

def inline(text):
    out = []
    pos = 0
    # protect inline code first
    for m in re.finditer(r'`([^`]+)`', text):
        out.append(_inline_no_code(text[pos:m.start()]))
        out.append('<code>' + html.escape(m.group(1)) + '</code>')
        pos = m.end()
    out.append(_inline_no_code(text[pos:]))
    return ''.join(out)


def _inline_no_code(text):
    t = html.escape(text)
    t = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',
               lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}">', t)
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
               lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)
    t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
    t = t.replace('--&gt;', '&rarr;').replace('&lt;-', '&larr;')
    return t


def slug(text):
    s = re.sub(r'<[^>]+>', '', inline(text))
    s = html.unescape(s)
    s = re.sub(r'[^\w\s-]', '', s).strip().lower()
    return re.sub(r'[\s_]+', '-', s) or 'section'

# ---------- block ----------

def convert(md):
    lines = md.split('\n')
    out, toc = [], []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # fenced code
        if stripped.startswith('```'):
            lang = stripped[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ''
            out.append(f'<pre><code{cls}>' +
                       html.escape('\n'.join(buf)) + '</code></pre>')
            continue

        # horizontal rule
        if re.fullmatch(r'-{3,}', stripped):
            out.append('<hr>')
            i += 1
            continue

        # heading
        m = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if m:
            lvl = len(m.group(1))
            text = m.group(2).strip()
            sid = slug(text)
            if lvl <= 2:
                # inline() already escapes; strip tags, keep entities as-is
                toc.append((lvl, sid, re.sub(r'<[^>]+>', '', inline(text))))
            out.append(f'<h{lvl} id="{sid}">{inline(text)}'
                       f'<a class="anchor" href="#{sid}">#</a></h{lvl}>')
            i += 1
            continue

        # table
        if stripped.startswith('|') and i + 1 < n and \
                re.fullmatch(r'\|[\s:|-]+\|', lines[i + 1].strip()):
            header = _row(stripped)
            i += 2
            body = []
            while i < n and lines[i].strip().startswith('|'):
                body.append(_row(lines[i].strip()))
                i += 1
            th = ''.join(f'<th>{inline(c)}</th>' for c in header)
            rows = ''.join(
                '<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>'
                for r in body)
            out.append('<div class="table-wrap"><table><thead><tr>'
                       f'{th}</tr></thead><tbody>{rows}</tbody>'
                       '</table></div>')
            continue

        # blockquote
        if stripped.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            paras = [p.strip() for p in '\n'.join(buf).split('\n\n')]
            inner = ''.join(
                f'<p>{inline(" ".join(p.split()))}</p>' for p in paras if p)
            out.append(f'<blockquote>{inner}</blockquote>')
            continue

        # unordered list
        if re.match(r'^-\s+', stripped):
            items, i = _list(lines, i, r'^-\s+')
            out.append('<ul>' + ''.join(f'<li>{inline(t)}</li>'
                                        for t in items) + '</ul>')
            continue

        # ordered list
        if re.match(r'^\d+\.\s+', stripped):
            items, i = _list(lines, i, r'^\d+\.\s+')
            out.append('<ol>' + ''.join(f'<li>{inline(t)}</li>'
                                        for t in items) + '</ol>')
            continue

        # paragraph: join wrapped lines until a blank or a new block
        buf = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        text = ' '.join(buf)
        body = inline(text)
        if re.fullmatch(r'<img [^>]+>', body):
            out.append(f'<figure>{body}</figure>')
        else:
            out.append(f'<p>{body}</p>')

    return '\n'.join(out), toc


def _is_block_start(line):
    s = line.strip()
    return (s.startswith('```') or s.startswith('|') or s.startswith('>')
            or s.startswith('#') or re.fullmatch(r'-{3,}', s)
            or re.match(r'^-\s+', s) or re.match(r'^\d+\.\s+', s))


def _list(lines, i, pattern):
    """Collect list items, folding indented continuation lines into the
    item they belong to (markdown lazy continuation)."""
    items = []
    n = len(lines)
    while i < n and re.match(pattern, lines[i].strip()):
        items.append(re.sub(pattern, '', lines[i].strip()))
        i += 1
        # absorb wrapped continuation lines: indented, not a new block
        while (i < n and lines[i].strip()
               and lines[i][:1] in ' \t'
               and not _is_block_start(lines[i])):
            items[-1] += ' ' + lines[i].strip()
            i += 1
    return items, i


def _row(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]

# ---------- page ----------

CSS = """
:root{
  --bg:#fbfbf9; --surface:#ffffff; --ink:#1c1c1a; --muted:#5c5c56;
  --line:#e3e3dd; --accent:#8a4b2a; --accent-soft:#f3ece7;
  --code-bg:#f5f4f0; --quote-bg:#f7f5f1;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#16161a; --surface:#1d1d22; --ink:#e8e8e4; --muted:#a0a099;
    --line:#32323a; --accent:#e0a077; --accent-soft:#2a2320;
    --code-bg:#232329; --quote-bg:#202026;
  }
}
:root[data-theme="dark"]{
  --bg:#16161a; --surface:#1d1d22; --ink:#e8e8e4; --muted:#a0a099;
  --line:#32323a; --accent:#e0a077; --accent-soft:#2a2320;
  --code-bg:#232329; --quote-bg:#202026;
}
*{box-sizing:border-box}
body{
  background:var(--bg); color:var(--ink); margin:0;
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
       "Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.layout{max-width:1180px;margin:0 auto;padding:0 24px;
  display:grid;grid-template-columns:236px minmax(0,1fr);gap:48px}
nav.toc{position:sticky;top:0;align-self:start;max-height:100vh;
  overflow-y:auto;padding:40px 0 40px;font-size:13.5px}
nav.toc .label{text-transform:uppercase;letter-spacing:.09em;
  font-size:11px;color:var(--muted);font-weight:700;margin-bottom:12px}
nav.toc a{display:block;color:var(--muted);text-decoration:none;
  padding:4px 10px;border-left:2px solid transparent;line-height:1.4}
nav.toc a:hover{color:var(--accent);border-left-color:var(--accent);
  background:var(--accent-soft)}
nav.toc a.lvl2{padding-left:22px;font-size:13px}
main{padding:40px 0 96px;min-width:0}
h1,h2,h3,h4{line-height:1.25;font-weight:650;
  scroll-margin-top:24px;position:relative}
h1{font-size:2.05rem;margin:.2em 0 .6em;letter-spacing:-.02em}
h2{font-size:1.5rem;margin:2.2em 0 .7em;padding-bottom:.3em;
  border-bottom:1px solid var(--line)}
h3{font-size:1.16rem;margin:1.9em 0 .5em}
h4{font-size:1rem;margin:1.5em 0 .4em;color:var(--muted)}
.anchor{position:absolute;margin-left:.4em;color:var(--line);
  text-decoration:none;opacity:0;font-weight:400}
h1:hover .anchor,h2:hover .anchor,h3:hover .anchor{opacity:1}
.anchor:hover{color:var(--accent)}
p{margin:0 0 1em}
a{color:var(--accent)}
ul,ol{margin:0 0 1.15em;padding-left:1.45em}
li{margin:.32em 0}
li::marker{color:var(--muted)}
hr{border:0;border-top:1px solid var(--line);margin:2.6em 0}
code{background:var(--code-bg);border:1px solid var(--line);
  border-radius:4px;padding:.12em .38em;font-size:.875em;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--code-bg);border:1px solid var(--line);
  border-radius:8px;padding:16px 18px;overflow-x:auto;margin:0 0 1.3em}
pre code{background:none;border:0;padding:0;font-size:13px;line-height:1.55}
blockquote{margin:0 0 1.3em;padding:14px 18px;background:var(--quote-bg);
  border-left:3px solid var(--accent);border-radius:0 8px 8px 0}
blockquote p{margin:0 0 .6em}
blockquote p:last-child{margin:0}
.table-wrap{overflow-x:auto;margin:0 0 1.5em;border:1px solid var(--line);
  border-radius:8px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);
  vertical-align:top}
th{background:var(--accent-soft);font-weight:650;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
figure{margin:0 0 1.6em;text-align:center}
img{max-width:100%;height:auto;border:1px solid var(--line);
  border-radius:8px;background:var(--surface)}
footer{margin-top:64px;padding-top:20px;border-top:1px solid var(--line);
  font-size:13px;color:var(--muted)}
@media (max-width:900px){
  .layout{grid-template-columns:1fr;gap:0}
  nav.toc{position:static;max-height:none;padding:28px 0 0;
    border-bottom:1px solid var(--line);margin-bottom:8px}
  nav.toc a.lvl2{display:none}
}
"""

TPL = """<!doctype html>
<html lang="en" data-theme-auto>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="layout">
<nav class="toc"><div class="label">On this page</div>
{toc}
</nav>
<main>
{body}
<footer>Extracted from the DOCUMENTATIONS export &middot; \
OSI model study notes &middot; see <code>README.md</code> for the \
markdown source.</footer>
</main>
</div>
</body>
</html>
"""


def main(src, dst, title):
    md = Path(src).read_text(encoding='utf-8')
    body, toc = convert(md)
    links = '\n'.join(
        f'<a class="lvl{lvl}" href="#{sid}">{txt}</a>'
        for lvl, sid, txt in toc if lvl >= 1)
    Path(dst).write_text(
        TPL.format(title=html.escape(title), css=CSS, toc=links, body=body),
        encoding='utf-8')
    print(f'{dst}  ({len(body.splitlines())} blocks, {len(toc)} toc entries)')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
