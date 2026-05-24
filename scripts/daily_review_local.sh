#!/bin/bash
# 每日艾宾浩斯复习（本机版）：算出今日到期/新学单词 → 生成 HTML → push 到 Pages → 发 Bark。
# 由 launchd (com.zuo.study-words-daily) 每天 19:07 触发；也可手动运行测试。
# 当天「无到期复习 且 无新词」时不发 Bark，避免打扰。
set -uo pipefail

REPO="/Users/zuo/magic/matrix/study-words"
ENV_FILE="$HOME/.video-mind/.env"
BARK_SCRIPT="$HOME/.claude/skills/bark-notify/scripts/bark_notify.py"
LOG="$REPO/scripts/daily-review.log"

exec >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 每日复习任务开始 ====="

cd "$REPO" || { echo "[ERR] repo 不存在"; exit 1; }

BARK_KEY=$(grep -E '^BARK_KEY=' "$ENV_FILE" | cut -d= -f2 | tr -d '"'"'"' ')
if [ -z "${BARK_KEY:-}" ]; then echo "[ERR] 未找到 BARK_KEY"; exit 1; fi

git pull --rebase -q origin main 2>&1 || echo "[WARN] pull 跳过"

# 生成今日复习页；脚本输出两行：第1行=相对路径，第2行=DUE=n NEW=m
OUTPUT=$(python3 scripts/build_review.py)
OUT_PATH=$(echo "$OUTPUT" | sed -n '1p')
STATS=$(echo "$OUTPUT" | sed -n '2p')
DUE=$(echo "$STATS" | sed -E 's/.*DUE=([0-9]+).*/\1/')
NEW=$(echo "$STATS" | sed -E 's/.*NEW=([0-9]+).*/\1/')
echo "生成: $OUT_PATH ($STATS)"

git -c user.name="zz-gl" -c user.email="oudizuo@gmail.com" add reviews/
git -c user.name="zz-gl" -c user.email="oudizuo@gmail.com" commit -m "Auto: daily review $(date +%Y-%m-%d) (due=$DUE new=$NEW)" 2>&1 || echo "无新提交"
git push -q origin main 2>&1 || echo "[WARN] push 失败"

PAGES_URL="https://zz-gl.github.io/study-words/${OUT_PATH}"

# 组织推送文案；都为 0 则不推
if [ "${DUE:-0}" -gt 0 ] 2>/dev/null; then
  BODY="今日 ${DUE} 个词到期复习"
  [ "${NEW:-0}" -gt 0 ] 2>/dev/null && BODY="${BODY} · ${NEW} 个新词"
  BODY="${BODY}，点开开始复习 →"
elif [ "${NEW:-0}" -gt 0 ] 2>/dev/null; then
  BODY="今日学了 ${NEW} 个新词，暂无到期复习 →"
else
  echo "今日 0 到期 0 新词，跳过推送"
  echo "===== $(date '+%H:%M:%S') 完成(未推送) ====="
  exit 0
fi

python3 "$BARK_SCRIPT" --key "$BARK_KEY" --title "📚 今日复习" --body "$BODY" --url "$PAGES_URL" --group "英语复习"
echo "===== $(date '+%H:%M:%S') 完成 ====="
