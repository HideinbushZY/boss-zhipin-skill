#!/usr/bin/env bash
# verify-setup.sh — boss-zhipin skill 用前一键自检
#
# 用法:
#   bash verify-setup.sh <browser_id> [session_name]
#   例: bash verify-setup.sh direct_local_xxxxxxxxxxxx boss-verify
#
# 查四关:① browser-act 可用 ② 浏览器 id 已设且存在 ③ Boss 登录态 ④ 每日额度/畅聊卡余量
# 输出 pass/fail;有 FAIL(exit≠0)就先解决再跑 skill。
# 设计遵循 SKILL.md 安全纪律:只开会话读一下、跑完关会话,绝不 --allow-restart-chrome(会登出)。

set -uo pipefail

PASS=0; FAIL=0; WARN=0
ok()   { printf '  \033[32m✅ %s\033[0m\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31m❌ %s\033[0m\n' "$1"; FAIL=$((FAIL+1)); }
warn() { printf '  \033[33m⚠️  %s\033[0m\n' "$1"; WARN=$((WARN+1)); }

BID="${1:-<YOUR_BROWSER_ID>}"
SESS="${2:-boss-verify}"

echo "== boss-zhipin skill · 用前自检 =="

# ── ① browser-act CLI ────────────────────────────────
if command -v browser-act >/dev/null 2>&1; then
  ok "browser-act 已安装（$(browser-act --version 2>/dev/null | head -1 || echo '版本未知')）"
  BA_OK=1
else
  bad "browser-act 未安装 → 'uv tool install browser-act-cli' 后配好 API key（见 BACKENDS.md 可换免费替代）"
  BA_OK=0
fi

# ── ①b python3 + PyYAML（validate.py 硬依赖，缺了 Step 0 校验直接挂）──
if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import yaml' >/dev/null 2>&1; then
    ok "python3 + PyYAML 就绪（validate.py 可跑）"
  else
    bad "缺 PyYAML → validate.py 跑不了（Step 0 策略校验会挂）：pip3 install pyyaml（或 python3 -m pip install pyyaml）"
  fi
else
  bad "未装 python3 → validate.py / scripts/notebook.py（候选人硬门 gate-action）都跑不了：先装 Python 3"
fi

# ── ② 浏览器 id ──────────────────────────────────────
if [ "$BID" = "<YOUR_BROWSER_ID>" ]; then
  bad "没传浏览器 id → 用法: bash verify-setup.sh <browser_id> [session]；查 id: 'browser-act browser list'"
  ID_OK=0
elif [ "$BA_OK" = 1 ] && browser-act browser list 2>/dev/null | grep -q "$BID"; then
  ok "chrome-direct 浏览器存在: $BID"
  ID_OK=1
else
  warn "'browser-act browser list' 里没找到 $BID（还没建就 'browser-act get-skills advanced' 按引导建 chrome-direct）"
  ID_OK=0
fi

# ── ③ 登录态（需 ①② 通过）───────────────────────────
NAME=""
if [ "$BA_OK" = 1 ] && [ "$ID_OK" = 1 ]; then
  echo "  … 打开工作台核对登录（会开一个 headed 会话，稍等 ~12s）"
  # 注意:用推荐页而非 /web/chat/index——后者冷加载会卡「加载中」(SKILL 铁律#3),
  # 会误判成未登录;推荐页冷加载正常、且同样有顶栏招聘者名 .user-name。
  browser-act --session "$SESS" browser open "$BID" "https://www.zhipin.com/web/chat/recommend" --headed >/dev/null 2>&1
  sleep 12
  # 先分清「Chrome 没接上」vs「到了 zhipin 但没登录」——两者提示完全不同
  ONZP=$(browser-act --session "$SESS" eval "location.href.indexOf('zhipin.com')>=0?'yes':'no'" 2>/dev/null | tr -d '"' | tail -1)
  NAME=$(browser-act --session "$SESS" eval "document.querySelector('.user-name')?.textContent||''" 2>/dev/null | tr -d '"' | tail -1)
  if [ "$ONZP" != "yes" ]; then
    bad "Chrome 没接上 / 没到 zhipin（不是登录问题）—— 确保该 Chrome 开着且能被 browser-act 接管；桥掉线时: browser open <id> <url> --headed --allow-restart-chrome（详见 operation-map「桥掉线恢复姿势」）"
  elif [ -n "$NAME" ] && [ "$NAME" != "null" ]; then
    ok "Boss 已登录，招聘者 = $NAME"
  else
    bad "到了 zhipin 但未登录 —— Boss 需手机扫码登录，agent 代替不了；请人工在该 Chrome 里登进去再重跑"
  fi

  # ── ④ 额度 / 畅聊卡余量（best-effort，读不到只 warn 不 fail）──
  if [ -n "$NAME" ] && [ "$NAME" != "null" ]; then
    QUOTA=$(browser-act --session "$SESS" eval "
      (async()=>{try{
        const r=await fetch('/wapi/zprelation/friend/manage/geekListV2?page=1&pageSize=1',{credentials:'include'});
        const j=await r.json(); return (j&&j.code===0)?'ok':'nocode';
      }catch(e){return 'err';}})()" 2>/dev/null | tr -d '"' | tail -1)
    if [ "$QUOTA" = "ok" ]; then
      ok "招聘接口可读（会话有效，额度/畅聊卡余量可在工作台或 geeks.json 的 chatCardCount 查）"
    else
      warn "招聘数据接口没读到（$QUOTA）——不影响基本操作，跑策略前在工作台确认下打招呼额度/畅聊卡余量"
    fi
  fi

  browser-act session close "$SESS" >/dev/null 2>&1
else
  warn "①/② 没过，跳过登录与额度检查"
fi

# ── 汇总 ─────────────────────────────────────────────
echo "== 结果: PASS=$PASS  FAIL=$FAIL  WARN=$WARN =="
if [ "$FAIL" -eq 0 ]; then
  echo "✅ setup 就绪，可以让 agent 读 SKILL.md 开跑。"
  exit 0
else
  echo "❌ 有 $FAIL 项 FAIL，先按上面提示解决再跑 skill。"
  exit 1
fi
