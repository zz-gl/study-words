#!/bin/bash
# 每周英语复习（本机版）：生成本周复习 HTML → push 到 GitHub Pages → 发 Bark 通知。
# 由 launchd (com.zuo.study-words-weekly) 每周六 19:07 触发；也可手动运行测试。
set -uo pipefail

REPO="/Users/zuo/magic/matrix/study-words"
ENV_FILE="$HOME/.video-mind/.env"
BARK_SCRIPT="$HOME/.claude/skills/bark-notify/scripts/bark_notify.py"
LOG="$REPO/scripts/weekly-review.log"

exec >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 周复习任务开始 ====="

cd "$REPO" || { echo "[ERR] repo 不存在"; exit 1; }

# 读取 Bark Key
BARK_KEY=$(grep -E '^BARK_KEY=' "$ENV_FILE" | cut -d= -f2 | tr -d '"'"'"' ')
if [ -z "${BARK_KEY:-}" ]; then echo "[ERR] 未找到 BARK_KEY"; exit 1; fi

# 同步最新（以防在别处编辑过）
git pull --rebase -q origin main 2>&1 || echo "[WARN] pull 跳过"

# 生成本周 HTML
OUT_PATH=$(python3 scripts/build_weekly_review.py)
echo "生成: $OUT_PATH"

# 提交并推送（更新 GitHub Pages）
git -c user.name="zz-gl" -c user.email="oudizuo@gmail.com" add reviews/
git -c user.name="zz-gl" -c user.email="oudizuo@gmail.com" commit -m "Auto: weekly review $(date +%Y-%m-%d)" 2>&1 || echo "无新提交"
git push -q origin main 2>&1 || echo "[WARN] push 失败"

PAGES_URL="https://zz-gl.github.io/study-words/${OUT_PATH}"

# 统计本周新增词数
N=$(python3 - <<'PY'
import datetime, re
today = datetime.date.today(); cut = today - datetime.timedelta(days=6)
t = open("vocabulary.md", encoding="utf-8").read()
m = re.search(r"## 新增日志[\s\S]+", t)
log = m.group(0) if m else ""
n = 0
for d, ws in re.findall(r"- \*\*(\d{4}-\d{2}-\d{2})\*\*[：:]\s*(.+)", log):
    if cut <= datetime.date.fromisoformat(d) <= today:
        n += len([x for x in ws.split(",") if x.strip()])
print(n)
PY
)
echo "本周词数: $N"

if [ "${N:-0}" -eq 0 ] 2>/dev/null; then
  BODY="本周没有新增单词，回顾一下旧词吧 💪"
else
  BODY="本周新增 ${N} 个词，点开查看本周复习页 →"
fi

python3 "$BARK_SCRIPT" --key "$BARK_KEY" --title "📚 英语周复习" --body "$BODY" --url "$PAGES_URL" --group "英语复习"
echo "===== $(date '+%H:%M:%S') 完成 ====="
