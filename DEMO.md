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

# 2) 接口读列表(主路径,抗改版)——清污染 jobId=0 + 关键词(operation-map §7e canonical 端点)
browser-act --session <S> eval "
  fetch('/wapi/zpitem/web/boss/search/geeks.json?keywords='+encodeURIComponent('会议系统前端算法')
    +'&jobId=0&page=1&source=1',{credentials:'include'}).then(r=>r.json())"
# → zpData.geeks[] 打码候选人 + 每人 geekCard.securityId + 顶层 chatCardCount 余量

# 3) 读排名第一者详情(接口=明文简历,破 canvas 反爬,比截图快一个量级)
browser-act --session <S> eval "fetch('/wapi/zpitem/web/boss/search/geek/info?securityId=<sid>&encryptGeekDetailGray=1'...)"
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
name: asr-engineer                        # 策略名(= 文件夹名)
linked_job: 语音识别(ASR)算法工程师       # 必须精确等于你已发布的在线职位名
rubric:
  must:                                   # 缺一 → 封顶 B
    - 3年以上语音/声学算法实战经验(ASR识别 或 会议前端声学 任一)
    - 掌握端到端语音识别原理 或 阵列/声学信号处理(会议前端)
touch_policy: report_first                # 安全默认:只研究零外发;升档 greet_*/full 需你授权
budget:
  greets_per_day: 15
  chat_cards: 0                           # 安全默认 0 卡;要开搜索畅聊须同时 authorize_card_pii_bundle: true
  authorize_card_pii_bundle: false        # chat_cards>0 必须显式 true(知情接受 PII 捆绑),validate.py 强制
intelligence:
  card_prescreen: { enabled: true }       # 默认开:花卡前免费打质量分,省无效卡
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
- 触达档:report_first(安全默认·零外发) · budget:打招呼15/天 · 畅聊卡0 · 详情40/轮 · 目标合格10
- 候选人（打码/脱敏示例）:
  - 某先生(示例) | 某声学公司·会议系统前端 | 28-35K·深圳 | 8.0 | 未触达(report_first 只研究不外发)
- 累计合格(A):2/目标10。本轮零外发(未打招呼、未花卡)。
- 下一步建议(等你拍板):授权升档 greet_* 打招呼 / 供给错配则上探薪资 / 放宽经验 / 授权畅聊卡(chat_cards>0 + authorize_card_pii_bundle)定向挖目标公司。
```

**闭环边界(诚实)**:管线**止于"收到简历"**;换电话/微信/约面 = **永久红线,只在报告里建议、等你点**。

---

## 你会看到的"安全刹车"(这是特性不是 bug)

- **默认零外发(report_first)**:新策略触达默认档 = `report_first`(只研究、给 A/B/C 名单+打分,不自动打招呼/求简历/花卡);要外发得你显式升档 `greet_*`/`full` 并授权。
- **候选人意图硬门(Phase 0)**:对某人 打招呼/求简历/继续发消息/花卡 前先过 `gate-action` 硬门——新回复先进 `pending_intent_review`,**没你确认 `interested` 前不自动求简历/跟进**;被标 `reject/no_interest/do_not_contact` 的人五类外发**硬阻断**(独立于错题本、错题本也解不开;见 `SAFETY.md` §8)。
- 任何**外发**(打招呼/回复/求简历)、**消耗畅聊卡**、**发布/关闭职位** → agent 发出前**逐条等你确认**。
- **换电话 / 换微信 / 约面 / 删除职位 / 举报** → 永久红线,agent 只导航到位、给步骤,**那一下由你亲自点**。
- 命中疑似风控 → agent **停手冷却**,不硬撞、不连环重启 Chrome。

完整规则见 [`SAFETY.md`](SAFETY.md);想看它为什么这么设计,见 README「现状与已知局限」。
