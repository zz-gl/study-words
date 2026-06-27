#!/bin/bash
# 每日艾宾浩斯复习（本机版）：算出今日到期/新学单词 → 生成 HTML → push 到 Pages → 发 Bark + 邮件。
# 由 launchd (com.zuo.study-words-daily) 每天 22:30 触发；也可手动运行测试。
# 当天「无到期复习 且 无新词」时跳过 Bark 与邮件，避免打扰。
set -uo pipefail

REPO="/Users/zuo/magic/matrix/study-words"
ENV_FILE="$HOME/.video-mind/.env"
BARK_SCRIPT="$HOME/.claude/skills/bark-notify/scripts/bark_notify.py"
AGENTLY="/Users/zuo/.npm-global/bin/agently-cli"
MAIL_TO="oudizuo_2026@qq.com"
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

# 邮件投递（agently-cli 两步确认：先拿 token，再带 token 真发）
DATE_STR=$(date +%Y-%m-%d)
SUBJECT="📚 今日复习 · ${DATE_STR} · 待复习 ${DUE} · 新学 ${NEW}"
TOKEN=$("$AGENTLY" message +send \
  --to "$MAIL_TO" \
  --subject "$SUBJECT" \
  --body-file "$OUT_PATH" 2>/dev/null | jq -r '.data.confirmation_token // empty')

if [ -n "$TOKEN" ]; then
  "$AGENTLY" message +send \
    --to "$MAIL_TO" \
    --subject "$SUBJECT" \
    --body-file "$OUT_PATH" \
    --confirmation-token "$TOKEN" 2>&1 | jq -r '"mail: queued=" + (.data.queued|tostring)' || echo "[WARN] 邮件发送失败"
else
  echo "[WARN] 未取到 confirmation_token，邮件未发"
fi

echo "===== $(date '+%H:%M:%S') 完成 ====="
