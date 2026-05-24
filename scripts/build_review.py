#!/usr/bin/env python3
"""Build a spaced-repetition (Ebbinghaus) daily review page from vocabulary.md.

For a target date (default today), find every word whose age since its
first-seen date (from the Daily Log) equals one of the review intervals,
plus words newly added today. Render reviews/review-YYYY-MM-DD.html grouped
by review stage. Print the output path (relative to repo root) on the first
stdout line, then a second line "DUE=<n> NEW=<m>" for the caller.

Usage: build_review.py [YYYY-MM-DD]
"""
from __future__ import annotations
import datetime
import html
import os
import re
import sys

# Ebbinghaus-inspired review ladder (days after first seen).
INTERVALS = [1, 2, 4, 7, 15, 30, 60, 90]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB = os.path.join(ROOT, "vocabulary.md")
OUT_DIR = os.path.join(ROOT, "reviews")
os.makedirs(OUT_DIR, exist_ok=True)

today = (
    datetime.date.fromisoformat(sys.argv[1])
    if len(sys.argv) > 1
    else datetime.date.today()
)

text = open(VOCAB, encoding="utf-8").read()

# --- Parse Daily Log: map each word to its first-seen date ---
log_match = re.search(r"## 新增日志[\s\S]+", text)
log_text = log_match.group(0) if log_match else ""
first_seen: dict[str, datetime.date] = {}
for date_str, words_str in re.findall(
    r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*[：:]\s*(.+)$", log_text, re.MULTILINE
):
    d = datetime.date.fromisoformat(date_str)
    for w in (x.strip() for x in words_str.split(",")):
        if w and w not in first_seen:
            first_seen[w] = d

# --- Bucket words by review stage for the target date ---
new_words: list[str] = []
buckets: dict[int, list[str]] = {n: [] for n in INTERVALS}
for w, d in first_seen.items():
    elapsed = (today - d).days
    if elapsed == 0:
        new_words.append(w)
    elif elapsed in buckets:
        buckets[elapsed].append(w)

due_total = sum(len(v) for v in buckets.values())


# --- Markdown entry parsing (same conventions as build_weekly_review.py) ---
def find_entry_block(word: str):
    pat = re.compile(r"^- \*\*" + re.escape(word) + r"\*\* ", re.MULTILINE)
    m = pat.search(text)
    if not m:
        return None, []
    lines = text[m.start():].split("\n")
    main, subs = lines[0], []
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
    s = html.escape(s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"<em>\1</em>", s)
    return s


def parse_main(main: str):
    m = re.match(r"^- \*\*([^*]+)\*\* (/[^/]*/) (.+?) — (.+)$", main)
    if not m:
        return None
    word, phon, pos_zh, en = m.groups()
    pm = re.match(r"^([a-zA-Z./()\- ]+(?:\([^)]+\))?)\s+(.+)$", pos_zh.strip())
    pos, zh = (pm.group(1).strip(), pm.group(2).strip()) if pm else ("", pos_zh.strip())
    return word, phon, pos, zh, en


def render_word(word: str) -> str:
    main, subs = find_entry_block(word)
    if not main:
        return f'<article class="word"><h2 class="w-word">{html.escape(word)}</h2></article>'
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


def render_section(title: str, badge_class: str, words: list[str]) -> str:
    if not words:
        return ""
    cards = "\n".join(render_word(w) for w in words)
    return f"""
<section class="stage">
  <h2 class="stage-title"><span class="stage-dot {badge_class}"></span>{html.escape(title)}<span class="stage-count">{len(words)} 词</span></h2>
  {cards}
</section>"""


# --- Assemble sections: reviews first (most-forgetting-risk), then new ---
sections = []
stage_styles = {1: "d1", 2: "d2", 4: "d4", 7: "d7", 15: "d15", 30: "d30", 60: "d60", 90: "d90"}
for n in INTERVALS:
    sections.append(
        render_section(f"第 {n} 天复习", stage_styles.get(n, "d30"), buckets[n])
    )
sections.append(render_section("今日新学", "new", new_words))
body_html = "\n".join(s for s in sections if s)

if not body_html:
    body_html = '<p class="empty">今天没有到期复习的单词，也没有新词 🎉<br>可以打开单词本随便翻翻旧词。</p>'

gen_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
subtitle = f"待复习 {due_total} 词"
if new_words:
    subtitle += f" · 今日新学 {len(new_words)} 词"

page = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>每日复习 · {today.isoformat()}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{
  --primary:#0f766e; --accent:#f59e0b; --bg:#f6fbfb; --surface:#fff;
  --fg-1:#10201f; --fg-2:#304c49; --fg-muted:#647b78; --border:rgba(15,118,110,.14);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--fg-1);
  font-family:'Plus Jakarta Sans',ui-sans-serif,system-ui,sans-serif;
  line-height:1.6;padding:24px 16px 60px;max-width:720px;margin:0 auto;-webkit-font-smoothing:antialiased}}
header.page{{margin-bottom:28px;text-align:center}}
.eyebrow{{font-size:11.5px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--primary)}}
h1.title{{font-family:'Space Grotesk',sans-serif;font-size:clamp(26px,7vw,36px);font-weight:700;
  letter-spacing:-.02em;margin:6px 0 8px;
  background:linear-gradient(115deg,#0f766e,#f59e0b);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}}
.meta{{font-size:13px;color:var(--fg-muted)}}
.stage{{margin-bottom:28px}}
.stage-title{{display:flex;align-items:center;gap:9px;font-family:'Space Grotesk',sans-serif;
  font-size:16px;font-weight:600;color:var(--fg-1);margin-bottom:14px;
  padding-bottom:8px;border-bottom:2px solid var(--border)}}
.stage-count{{margin-left:auto;font-size:12px;font-weight:600;color:var(--fg-muted);
  font-family:'Plus Jakarta Sans',sans-serif}}
.stage-dot{{width:11px;height:11px;border-radius:50%;flex:none}}
.stage-dot.new{{background:#0f766e}} .stage-dot.d1{{background:#ef4444}}
.stage-dot.d2{{background:#f97316}} .stage-dot.d4{{background:#f59e0b}}
.stage-dot.d7{{background:#eab308}} .stage-dot.d15{{background:#84cc16}}
.stage-dot.d30{{background:#10b981}} .stage-dot.d60{{background:#14b8a6}}
.stage-dot.d90{{background:#3b82f6}}
article.word{{background:var(--surface);border:1px solid var(--border);border-radius:18px;
  padding:18px 20px;margin-bottom:14px;box-shadow:0 2px 8px rgba(16,32,31,.04)}}
.w-head{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:8px}}
.w-word{{font-family:'Space Grotesk',sans-serif;font-size:23px;font-weight:700;letter-spacing:-.01em}}
.w-phon{{font-family:'SF Mono',ui-monospace,monospace;font-size:13.5px;color:var(--primary)}}
.w-pos{{display:inline-block;font-size:12px;padding:2px 9px;border-radius:999px;
  background:#e6f2ef;color:var(--primary);font-weight:600;margin-right:6px}}
.w-zh{{font-size:18px;font-weight:600;margin-bottom:6px}}
.w-en{{font-size:13.5px;color:var(--fg-2);font-style:italic;
  padding-left:12px;border-left:3px solid var(--accent);margin-bottom:12px}}
.w-subs{{list-style:none;display:flex;flex-direction:column;gap:6px;
  padding-top:12px;border-top:1px dashed var(--border)}}
.w-subs li{{font-size:13.5px;color:var(--fg-2);line-height:1.55}}
.w-subs li strong{{color:var(--primary);font-weight:600}}
.w-subs code{{font-family:'SF Mono',monospace;font-size:.9em;background:#edf7f5;padding:1px 5px;border-radius:5px}}
.empty{{text-align:center;color:var(--fg-muted);padding:50px 20px;
  background:var(--surface);border-radius:18px;border:1px solid var(--border);line-height:2}}
footer.foot{{text-align:center;font-size:11.5px;color:var(--fg-muted);margin-top:36px}}
footer.foot a{{color:var(--primary);text-decoration:none}}
</style>
</head>
<body>
<header class="page">
  <div class="eyebrow">艾宾浩斯每日复习</div>
  <h1 class="title">今日复习 · {today.strftime('%m-%d')}</h1>
  <div class="meta">{subtitle} · 生成于 {gen_at}</div>
</header>
<main>
{body_html}
</main>
<footer class="foot">
  间隔阶梯 1·2·4·7·15·30·60·90 天 · <a href="https://github.com/zz-gl/study-words">源仓库</a>
</footer>
</body>
</html>
"""

out_path = os.path.join(OUT_DIR, f"review-{today.isoformat()}.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(page)

print(os.path.relpath(out_path, ROOT))
print(f"DUE={due_total} NEW={len(new_words)}")
