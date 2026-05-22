#!/usr/bin/env python3
"""Build a weekly review HTML page from vocabulary.md's Daily Log.

Reads vocabulary.md, extracts words added in the last 7 days, and writes
reviews/review-YYYY-MM-DD.html. Prints the output path (relative to repo
root) to stdout so the calling routine can use it.
"""
from __future__ import annotations
import datetime
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB = os.path.join(ROOT, "vocabulary.md")
OUT_DIR = os.path.join(ROOT, "reviews")
os.makedirs(OUT_DIR, exist_ok=True)

today = datetime.date.today()
cutoff = today - datetime.timedelta(days=6)  # last 7 days inclusive

text = open(VOCAB, encoding="utf-8").read()

# --- Parse Daily Log section ---
log_match = re.search(r"## 新增日志[\s\S]+", text)
log_text = log_match.group(0) if log_match else ""
log_lines = re.findall(
    r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*[：:]\s*(.+)$", log_text, re.MULTILINE
)

recent_words: list[str] = []
for date_str, words_str in log_lines:
    d = datetime.date.fromisoformat(date_str)
    if cutoff <= d <= today:
        for w in (x.strip() for x in words_str.split(",")):
            if w:
                recent_words.append(w)


def find_entry_block(word: str):
    """Find the entry block (main bullet + sub-bullets) for a word."""
    pat = re.compile(r"^- \*\*" + re.escape(word) + r"\*\* ", re.MULTILINE)
    m = pat.search(text)
    if not m:
        return None, []
    lines = text[m.start():].split("\n")
    main = lines[0]
    subs: list[str] = []
    for line in lines[1:]:
        if line.startswith("  - "):
            subs.append(line[4:])
        elif line.startswith("    "):
            if subs:
                subs[-1] += " " + line.strip()
        elif line.startswith("- ") or line.startswith("##") or line.startswith("---"):
            break
        elif line.strip() == "":
            break
    return main, subs


def md_lite(s: str) -> str:
    """Minimal markdown -> HTML: escape, then **bold** and `code`."""
    s = html.escape(s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"<em>\1</em>", s)  # [[link]] → em
    return s


def parse_main(main: str):
    """Parse '- **word** /phon/ pos. zh — en' into pieces."""
    m = re.match(
        r"^- \*\*([^*]+)\*\* (/[^/]*/) (.+?) — (.+)$", main
    )
    if not m:
        return None
    word, phon, pos_zh, en = m.groups()
    pm = re.match(r"^([a-zA-Z./()\- ]+(?:\([^)]+\))?)\s+(.+)$", pos_zh.strip())
    if pm:
        pos, zh = pm.group(1).strip(), pm.group(2).strip()
    else:
        pos, zh = "", pos_zh.strip()
    return word, phon, pos, zh, en


def render_word(word: str) -> str:
    main, subs = find_entry_block(word)
    if not main:
        return f'<article class="word"><h2 class="w-word">{html.escape(word)}</h2><p class="w-en">(未在词条正文中找到)</p></article>'
    parsed = parse_main(main)
    if not parsed:
        return ""
    w, phon, pos, zh, en = parsed
    sub_html = "\n".join(f"<li>{md_lite(s)}</li>" for s in subs)
    sub_block = f'<ul class="w-subs">{sub_html}</ul>' if sub_html else ""
    return f"""
<article class="word">
  <header class="w-head">
    <h2 class="w-word">{html.escape(w)}</h2>
    <span class="w-phon">{html.escape(phon)}</span>
  </header>
  <div class="w-zh"><span class="w-pos">{html.escape(pos)}</span> {html.escape(zh)}</div>
  <div class="w-en">{html.escape(en)}</div>
  {sub_block}
</article>"""


words_html = "\n".join(render_word(w) for w in recent_words)
count = len(recent_words)
range_str = f"{cutoff.isoformat()} ~ {today.isoformat()}"
gen_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

if count == 0:
    words_html = '<p class="empty">本周没有新增单词，回顾一下旧词吧 💪</p>'

page = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每周复习 · {today.isoformat()}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{
  --primary:#0f766e; --accent:#f59e0b;
  --bg:#f6fbfb; --surface:#fff;
  --fg-1:#10201f; --fg-2:#304c49; --fg-muted:#647b78;
  --border:rgba(15,118,110,.14);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--fg-1);
  font-family:'Plus Jakarta Sans',ui-sans-serif,system-ui,sans-serif;
  line-height:1.6;padding:24px 16px 60px;max-width:720px;margin:0 auto;
  -webkit-font-smoothing:antialiased}}
header.page{{margin-bottom:32px;text-align:center}}
.eyebrow{{font-size:11.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--primary)}}
h1.title{{font-family:'Space Grotesk',sans-serif;font-size:clamp(26px,7vw,36px);font-weight:700;
  letter-spacing:-.02em;margin:6px 0 8px;
  background:linear-gradient(115deg,#0f766e,#f59e0b);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.meta{{font-size:13px;color:var(--fg-muted)}}
article.word{{background:var(--surface);border:1px solid var(--border);border-radius:18px;
  padding:20px 22px;margin-bottom:18px;box-shadow:0 2px 8px rgba(16,32,31,.04)}}
.w-head{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:8px}}
.w-word{{font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;letter-spacing:-.01em;color:var(--fg-1)}}
.w-phon{{font-family:'SF Mono',ui-monospace,monospace;font-size:13.5px;color:var(--primary)}}
.w-pos{{display:inline-block;font-size:12px;padding:2px 9px;border-radius:999px;
  background:#e6f2ef;color:var(--primary);font-weight:600;margin-right:6px}}
.w-zh{{font-size:18px;font-weight:600;color:var(--fg-1);margin-bottom:6px}}
.w-en{{font-size:13.5px;color:var(--fg-2);font-style:italic;
  padding-left:12px;border-left:3px solid var(--accent);margin-bottom:14px}}
.w-subs{{list-style:none;display:flex;flex-direction:column;gap:6px;
  padding-top:12px;border-top:1px dashed var(--border)}}
.w-subs li{{font-size:13.5px;color:var(--fg-2);line-height:1.55}}
.w-subs li strong{{color:var(--primary);font-weight:600}}
.w-subs code{{font-family:'SF Mono',monospace;font-size:.9em;background:#edf7f5;padding:1px 5px;border-radius:5px}}
.empty{{text-align:center;color:var(--fg-muted);padding:40px 20px;
  background:var(--surface);border-radius:18px;border:1px solid var(--border)}}
footer.foot{{text-align:center;font-size:11.5px;color:var(--fg-muted);margin-top:36px}}
footer.foot a{{color:var(--primary);text-decoration:none}}
</style>
</head>
<body>
<header class="page">
  <div class="eyebrow">每周英语复习</div>
  <h1 class="title">本周 {count} 个新词</h1>
  <div class="meta">{range_str} · 生成于 {gen_at}</div>
</header>
<main>
{words_html}
</main>
<footer class="foot">
  由 study-words routine 自动生成 · <a href="https://github.com/zz-gl/study-words">源仓库</a>
</footer>
</body>
</html>
"""

out_path = os.path.join(OUT_DIR, f"review-{today.isoformat()}.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(page)

# Print only relative path so the calling shell can use it cleanly
print(os.path.relpath(out_path, ROOT))
