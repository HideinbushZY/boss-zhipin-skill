# DEMO — 用起来什么样(合成示例)

> ⚠️ **为什么是文字演示、不是真账号截图**:这个 skill 驱动真实 Boss直聘工作台,页面上全是**真实求职者个人信息**(姓名/经历/期望/联系方式)。往公开仓放真账号截图/GIF = 泄露第三方 PII。所以这里用 `strategies/asr-engineer-example/` 的**合成脱敏数据**做一次标注走查;真跑时把 `<占位>` 换成你自己的即可。

演示两种触发。命令用 browser-act 语法(换等价工具见 `BACKENDS.md`);`<BID>` = 你的浏览器 id,`<S>` = 会话名。

---

## 场景 A — 单点操作:"帮我搜'会议系统前端算法'的人,打开排名第一的简历"

**你对 agent 说**:
> 帮我在 Boss 上搜"会议系统前端算法",看看排第一的候选人简历。

**agent 做的(读 operation-map §2B/§7e)**:

```
# 1) 自检(可选)
bash verify-setup.sh <BID>            # → ✅ browser-act / ✅ 浏览器id / ✅ 已登录

# 2) 接口读列表(主路径,抗改版)——清污染 jobId=0 + 关键词
browser-act --session <S> eval "
  fetch('/wapi/zpgeek/search/geek/list.json?query='+encodeURIComponent('会议系统前端算法')
    +'&jobId=0&page=1',{credentials:'include'}).then(r=>r.json())"
# → 返回打码候选人列表 + 每人 securityId + 当次开聊成本

# 3) 读排名第一者详情(接口=明文简历,比截图快一个量级)
browser-act --session <S> eval "fetch('/wapi/zpgeek/geek/info.json?securityId=<sid>'...)"
```

**agent 回你**(合成示例):
> 排第一:**某先生(示例·打码)** · 某声学公司·会议系统前端算法 · 深圳 · 期望 28–35K。
> 亮点:会议系统 AEC/DOA/BF/NS 前端声学 + 端侧优化,与"会议转写"方向高度对口。
> 要不要打招呼?(免费)或用畅聊卡开聊(**逐人 1~3 张 + 会自动索要简历/微信/电话**,需你确认)。

> **注意红线**:开聊/打招呼这类外发,agent **停在这里等你点头**,不自作主张(SKILL.md 安全门)。

---

## 场景 B — 策略寻访:"按这个 JD 从目标公司挖 ASR 工程师"

**你给 agent** 一段 JD / 目标公司 / 能力要求。agent 读 `playbook.md`,把它落成一份策略(参照 `strategies/asr-engineer-example/strategy.yaml`):

```yaml
# strategies/asr-engineer-example/strategy.yaml(节选,已是仓里的合成示例)
role: "语音识别(ASR)算法工程师"
linked_job: "语音识别(ASR)算法工程师"     # 必须精确等于你已发布的在线职位名
rubric:
  must: ["3年+ ASR/语音算法", "端侧或会议场景优先"]
touch_policy: greet_recommend            # 推荐通道免费打招呼;付费开聊要单独授权
budget:
  greets_per_day: 15
  chat_cards: 12                         # 逐人 1~3 张,读 searchChatCardCostCount
  authorize_card_pii_bundle: true        # chat_cards>0 必须显式 true(知情接受 PII 捆绑)
intelligence:
  card_prescreen: { enabled: true }      # 默认开:花卡前免费打质量分,省无效卡
```

**跑前机检**:
```
python3 validate.py strategies/asr-engineer-example/
# → ✅ 校验通过（缺 must / touch_policy 拼错 / 开 salary_leverage 没给 base 都会在这报出来）
```

**agent 跑单轮管线**(playbook Step 1→6):**解析 → 找人[推荐/搜索] → LLM 打分 A/B/C → 按档触达 → 落报告**,状态写 `ledger.jsonl`(增量、去重)。

**产出的报告**长这样(仓里就有:`strategies/asr-engineer-example/reports/round-1-example.md`,合成数据):

```
# 寻访报告 · 语音识别(ASR)算法工程师 · 第1轮(示例)
- budget:打招呼15/天 · 畅聊卡预算N · 详情40/轮 · 目标合格10
- 候选人（打码/脱敏示例）:
  - 某先生(示例) | 某声学公司·会议系统前端 | 28-35K·深圳 | 8.0 | ✅畅聊卡开聊(消耗3卡)
- 累计合格(A):2/目标10。畅聊卡本轮用 3 张。今日打招呼 1/15。
- 下一步建议(等你拍板):供给错配则上探薪资 / 放宽经验 / 畅聊卡定向挖目标公司。
```

**闭环边界(诚实)**:管线**止于"收到简历"**;换电话/微信/约面 = **永久红线,只在报告里建议、等你点**。

---

## 你会看到的"安全刹车"(这是特性不是 bug)

- 任何**外发**(打招呼/回复/求简历)、**消耗畅聊卡**、**发布/关闭职位** → agent 发出前**逐条等你确认**。
- **换电话 / 换微信 / 约面 / 删除职位 / 举报** → 永久红线,agent 只导航到位、给步骤,**那一下由你亲自点**。
- 命中疑似风控 → agent **停手冷却**,不硬撞、不连环重启 Chrome。

完整规则见 [`SAFETY.md`](SAFETY.md);想看它为什么这么设计,见 README「现状与已知局限」。
