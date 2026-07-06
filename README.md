# boss-zhipin — Boss直聘招聘者侧操作 + 策略驱动寻访引擎(可复用 skill)

> A reusable Claude skill that turns an agent into a Boss直聘 (Chinese recruiting platform) **recruiter-side** operator: it drives a real logged-in Chrome to search/greet/screen candidates, and runs a strategy-driven sourcing pipeline (parse JD → find → LLM-score → reach out → report) with a local ledger for incremental runs. All page maps and selectors were verified by live operation on a real account.

一个可复用的 Claude skill:让 agent 像 **Boss直聘招聘者侧的熟手** 一样操作工作台,并把一段"搜索策略"跑成 `解析→找人→打分→触达→报告` 的自动寻访管线。页面地图和选择器全部真机实测过。

`License: MIT` · `Platform: Boss直聘 (zhipin.com), recruiter side` · `Driver: browser-act (chrome-direct)`

---

## English (TL;DR)

**What it is.** A reusable Claude/agent skill that operates the **recruiter side** of Boss直聘 (China's largest recruiting platform). Two modes: (A) point-ops — search candidates, read résumés, greet, reply, request résumé, post/manage jobs; (B) strategy sourcing — give it a JD / target companies / required skills and it runs a pipeline: **parse → find (recommend + paid search) → LLM-score (A/B/C) → reach out (per policy) → report**, with a local JSONL ledger for incremental, deduped runs.

**Structure (3 layers).** `SKILL.md` (triggers + iron rules + safety gates) → `operation-map.md` (execution layer: exact page selectors, all live-verified) → `playbook.md` (orchestration: the sourcing pipeline & scoring rubric). Example strategy under `strategies/asr-engineer-example/` (synthetic data).

**Prerequisites.** (1) the [browser-act](https://github.com/browser-act/skills) CLI (or any equivalent that can take over a logged-in Chrome via CDP, read the DOM, and do real clicks); (2) a logged-in Boss直聘 **recruiter** account, accessed via browser-act's `chrome-direct`; (3) a Claude-class agent as the brain.

**Setup (3 steps).** Drop `boss-zhipin/` into your skills dir → replace the `<YOUR_BROWSER_ID>` placeholder (run `browser-act browser list`) → verify login. See the Chinese sections below for the full operational detail.

> ⚠ **The operational docs are in Chinese on purpose** — Boss直聘's UI is Chinese and the selectors match Chinese on-page text, so the how-to-click content stays in Chinese. This English section is for discoverability; the working knowledge is in `SKILL.md` / `operation-map.md` / `playbook.md`.

**Safety.** Hard red lines that never auto-fire (report only): swap phone / swap WeChat / schedule interview / publish·close·delete jobs / report·bulk-reject. Outreach and paid actions (chat-cards) are gated by the strategy's `touch_policy` / `budget`. Rate-limit and back off on any risk-control signal.

**Maturity (honest).** A **qualified single-job sourcing engine** — the core recommend-channel loop (find→score→greet→dedup→receipt-scan→report) is battle-tested over 7 real-account rounds. Boundaries, on purpose: the loop **ends at "résumé received"**; **换电话/微信 is a permanent red line, never auto** (the paid-search "开聊" bundles a platform request for résumé/WeChat/phone, so `chat_cards>0` requires an explicit `authorize_card_pii_bundle: true`, enforced by `validate.py`); **约面 is untested** (red line). The operator-intuition layer (custom greetings / feedback loop / salary-flex / card prescreen) is implemented and its **logic validated on real data**, but **not yet validated with a real outbound send**. It is a sourcing engine for one recruiter — **not a complete recruiting platform** (no interview/offer, no heartbeat, single-job). See "现状与已知局限" below.

---

## 这是什么 / 三层结构

| 文件 | 层 | 作用 |
|---|---|---|
| **SKILL.md** | 触发头 | 什么时候用、四条操作铁律、安全门(红线)。你的 agent 先读它。 |
| **operation-map.md** | 执行层 | 每个页面怎么点、全部实测选择器、踩坑速查、健康检查/扫回执/清默认等确切步骤。 |
| **playbook.md** | 编排层 | 把策略解析成配置 → 找人[推荐/搜索/互动] → LLM 打分 A/B/C → 按档触达 → 落报告。 |
| **strategies/asr-engineer-example/** | 示例 | 一个填好的策略样例:`strategy.yaml`(配置)+ `ledger.example.jsonl`(账本 schema)+ `reports/`(报告格式)。**均为脱敏示例数据,非真实候选人。** |

---

## 用前提(prerequisites)

1. **browser-act CLI**(BrowserAct 家的浏览器自动化 CLI):`uv tool install browser-act-cli`,并配好 API key。skill 靠它接管你本机已登录的真实 Chrome。
   - 也可换成任何"能接管已登录 Chrome、能读 DOM + 真实点击"的等价工具;文中命令是 browser-act 语法,选择器/流程是通用的。**免费/开源替代(Playwright 扩展、claude-in-chrome、chrome-devtools-mcp 等)的实测对比、能力契约、动词映射见 [`BACKENDS.md`](BACKENDS.md)**——诚实结论:能力对等、能去掉 API-key 依赖,但装配摩擦不比 browser-act 低。
2. **一个已登录的 Boss直聘招聘者账号**,通过 browser-act 的 **chrome-direct**(接管本机 Chrome)访问。企业招聘者身份(能发职位/看推荐牛人/搜索牛人)。
3. Claude(或同类)agent 作为大脑跑 playbook 的判断/打分。

## 装配(3 步,照 SKILL.md「用前必做」)

1. 把 `boss-zhipin/` 整个文件夹放进你的 skills 目录(如 `~/.claude/skills/boss-zhipin/`),或直接让 agent 读 `SKILL.md` 入口。
2. **换浏览器 id**:`browser-act browser list` 查你自己的 chrome-direct id,**替换 operation-map 全文的 `<YOUR_BROWSER_ID>` 占位符**。若还没有 chrome-direct 浏览器,`browser-act get-skills advanced` 按引导建。
3. **确认登录**:先开会话——`browser-act --session <名> browser open <你的浏览器id> https://www.zhipin.com/web/chat/index --headed`;再 `browser-act --session <名> eval "document.querySelector('.user-name')?.textContent"` 应返回你的招聘者姓名(Boss 登录本身要手机扫码,只能人来做)。

## 怎么用(两种触发)

- **单点操作**("帮我搜X/给谁打招呼/发个岗位/回消息/求简历"):agent 读 `operation-map.md`,按选择器直接操作。
- **策略寻访**("按这段 JD / 从这几家挖某类人 / 找具备X能力的人,帮我找"):agent 读 `playbook.md`,把策略写成 `strategies/<name>/strategy.yaml`,跑单轮管线,状态写 `ledger.jsonl`,报告落 `reports/`。参照 `asr-engineer-example/`。

---

## ⚠ 安全红线(硬规则,任何模式任何档位都不自动)

**换电话 / 换微信 / 约面 / 发布·关闭·删除职位 / 举报 / 批量标记不合适** —— 这些最深的 PII/承诺/破坏性动作**只在报告里给建议,等人来点**。
- 外发内容(打招呼/回复/求简历)与消耗权益(畅聊卡)在策略里用 `touch_policy` / `budget` 授权;用户没授权就不做。
- **搜索畅聊卡"开聊" = 消耗 3 张 + 自动"索要简历/微信/电话"**(内置了换微信/电话的 PII 请求)——用它前必须让用户知情并接受这个捆绑。
- 低频、限速、分批:招聘方账号有行为风控;命中疑似风控就停手冷却,别连续重启 Chrome(可能触发登出,登出需用户手机扫码,agent 代替不了)。

---

## 现状与已知局限(诚实版,别当银弹)

这个 skill 经过一次真账号多轮实战 + 独立评审,**成熟度定级 functional(操作层可靠,但还不是"招聘经营专家")**。用之前知道它:

**已跑通/可靠**:发职位、推荐通道找人、搜索通道(免费打招呼 + 付费畅聊卡)、会话回复、求简历、LLM 打分判档、本地账本增量、扫回执(沟通中漏斗)、健康检查(打招呼额度/畅聊卡余量)、桥掉线恢复。

**还差 / 待补**:
- **约面(`.interview`)发起流程**未实测(红线不自动,但操作本身待文档化)。
- **接口层(XHR)**:推荐/搜索两条读通道已接口化为主路径(operation-map §7e);会话/发消息走 WebSocket 无干净 REST,写路径刻意保留 UI(确认框/提示门=安全闸)。
- **招聘运营直觉**已落地为可选智能层(定制招呼语/反馈环/薪资破格默认关、花卡预判默认开,playbook §11)+ 全局去重(operation-map §7f);仍缺:最佳触达时段、跨轮自动调参(反馈环只建议不自动改)、智能层整轮真机实测(逻辑已用真实数据验证、未真实外发)。
- 页面改版后选择器会腐烂,需重新验证。

**边界**:定位是"单次 + 单岗策略引擎"。不含:定时心跳持续运行、群发、offer/入职跟踪、与外部 ATS/HRIS 集成。

---

## 常见问题(FAQ)

**Q: 怎么换成我自己的浏览器 id?**
A: `browser-act browser list` 看你的 chrome-direct id,把 operation-map 里的 `<YOUR_BROWSER_ID>` 全替换。没有 chrome-direct 浏览器就 `browser-act get-skills advanced` 按引导建一个。

**Q: 跑着跑着账号登出了怎么办?**
A: chrome-direct 接管的是你真实登录的 Chrome,Boss 会话会自然过期、或被重启 Chrome 冲掉。登出后是**微信扫码/短信验证码**页,agent 代替不了——你手机扫码重登即可。⚠ 别让 agent 在 Chrome 0 窗口时 `--allow-restart-chrome`(极易登出)。

**Q: 某个操作点不动 / 选择器报错?**
A: 大概率 Boss 改版了、类名变了。诊断步骤和贡献方式见 `CONTRIBUTING.md`;优先能用接口(§7e:`rec/geek/list`/`geeks.json`)就别靠 DOM 选择器(接口抗改版一个数量级)。

**Q: 搜索畅聊卡"开聊"怎么这么贵?**
A: **每次开聊消耗 3 张**(不是 1),而且自动"发起沟通 + 索要简历/微信/电话"(捆绑 PII 请求,碰红线)。余量在搜索结果详情右侧「畅聊卡 剩余次数 xN」。用前务必知情——见 `SAFETY.md`。

**Q: 求简历按钮是灰的点不动?**
A: 平台前置门——候选人**回复前**(会话 `[送达]`/`[已读]`)求简历 disabled,必须对方回复进「沟通中」才解锁。别用 eval 强点。

**Q: linked_job 配了推荐通道还是不出人?**
A: 确认 `linked_job` 精确等于你已发布的在线职位名;推荐流打开时有默认预选,或职位 encJobId 没对上。校验配置用 `python3 validate.py strategies/<name>/`。

**Q: strategy.yaml 写错了怎么早点发现?**
A: 跑前 `python3 validate.py strategies/<name>/`,会报"缺 rubric.must / touch_policy 拼错 / 开 salary_leverage 没给 base_salary_range"这类具体错。schema 在 `schemas/`。

**Q: 多个 agent / 我自己也在用这个 Chrome,会冲突吗?**
A: chrome-direct **接管期间独占**你的 Chrome,你手动操作会打架。跑寻访时别同时手动操作同一个 Chrome;跑完 `browser-act session close <名>` 释放。

**Q: 桥掉线报 `230404 Unknown error`?**
A: browser-act 控制面/CDP 问题,不是账号封禁(`stealth-extract` 还能用就说明 cloud 没挂)。等 Chrome 完全就绪(AppleScript 能 count windows),再 `browser open <id> <url> --headed --allow-restart-chrome` 重试。详见 operation-map「桥掉线恢复姿势」。

**Q: 智能层(定制招呼语 / 反馈环 / 薪资破格 / 花卡预判)怎么开?**
A: 在 strategy.yaml 的 `intelligence:` 块改对应 `enabled`。**`card_prescreen` 默认就是开的**(只减花卡、零外发,越保护越好);另外三把 `feedback` / `custom_greetings` / `salary_leverage` 默认关,建议顺序 ①feedback → ②custom_greetings → ③salary_leverage 逐个翻 `true`。逻辑见 playbook §11。

---

## 隐私说明

本包内示例策略的 `ledger.example.jsonl` 与 `reports/` **全部是虚构脱敏数据**;core 文档里的账号/公司/招聘者/地址/邮箱/真实候选人姓名均已抹除或换成占位符。真机跑出来的候选人数据请自己妥善保管、勿外发(涉及求职者个人信息)。

仓库自带 `.gitignore`,已默认忽略真跑产生的 `ledger.jsonl` 与非示例的 `reports/*.md`(以及简历附件/截图)——**照它用就不会误把候选人 PII 提交上来**。

---

## License

[MIT](./LICENSE) © 2026 HideinbushZY. 自由使用/修改/分发。按现状提供,不担保;操作真实招聘账号有风控风险,自行评估。
