#!/usr/bin/env bash
# preview 冒烟：把服务真起起来，用真实数据链路验一遍（不需要 Docker、不需要 Playwright）
# 用法：bash preview_smoke.sh /mnt/d/Hermes-Workspace/01-Projects/AutoInfo
# 退出码：0 全过；1 有断言失败；2 服务起不来（环境问题，不是产品问题）
set -uo pipefail
REPO="${1:-.}"
PORT="${PORT:-18000}"
Q="${Q:-test}"
cd "$REPO" || exit 2

PY=".venv/bin/python"
[ -x "$PY" ] || { echo "❌ 没有 .venv/bin/python"; exit 2; }

"$PY" -m uvicorn autoinfo.api.server:app --port "$PORT" --log-level warning >/tmp/preview_smoke.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT

for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:$PORT/health" || true)
  [ "$code" = "200" ] && break
  sleep 1
done
[ "$code" = "200" ] || { echo "❌ 服务 30s 内没起来（详见 /tmp/preview_smoke.log）"; tail -5 /tmp/preview_smoke.log; exit 2; }

fail=0
chk() { if [ "$1" = "1" ]; then echo "  ✅ $2"; else echo "  ❌ $2"; fail=1; fi; }

# ① 健康 + 版本与 pyproject 一致
health=$(curl -s --max-time 5 "http://127.0.0.1:$PORT/health")
ver=$(printf '%s' "$health" | "$PY" -c 'import sys,json;print(json.load(sys.stdin).get("version",""))' 2>/dev/null)
want=$("$PY" -c 'import autoinfo;print(getattr(autoinfo,"__version__",""))' 2>/dev/null)
[ "$ver" = "$want" ] && chk 1 "/health 200 且版本一致（$ver）" || chk 0 "/health 版本不一致：API=$ver pyproject=$want"

# ② 首页真渲染
body=$(curl -s --max-time 8 "http://127.0.0.1:$PORT/")
printf '%s' "$body" | grep -q "<title>AutoInfo Dashboard" && chk 1 "首页含 title（$(printf '%s' "$body" | wc -c) bytes）" || chk 0 "首页缺 title"

# ③ 真实数据链路：搜索必须拿回条目（这条比单测更接近"用户看到的效果"）
search=$(curl -s --max-time 15 "http://127.0.0.1:$PORT/api/v1/search?q=$Q")
n=$(printf '%s' "$search" | "$PY" -c 'import sys,json;d=json.load(sys.stdin);print(len((d.get("data") or {}).get("entries") or []))' 2>/dev/null || echo err)
if [ "$n" = "err" ] || [ "$n" = "0" ]; then
  chk 0 "搜索没有返回条目（q=$Q, n=$n）—— 若是干净库，需先 seed"
else
  chk 1 "搜索返回 $n 条（q=$Q，真实 DB 链路通）"
fi

echo "—— preview 冒烟 $([ $fail = 0 ] && echo 全过 || echo 有失败)"
exit $fail
