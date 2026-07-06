# Roadmap — boss-zhipin

> 后续改进建议,分**代码/工程层面**与**功能/产品层面**,按优先级(影响高 + 工作量小者靠前)。每条可直接开成一个 issue。
>
> **一句话定位**:操作层已实战淬炼、自洽。现在卡在两道坎——工程上"代码形态的东西还散在 markdown 里",产品上"会点按钮但还不懂招聘"。下一步最该使劲:把 DOM 遍历换成**接口主路径**(救可靠性),同时补**开源就绪度**(救采纳率)。
>
> 工作量:`S`=小 / `M`=中 / `L`=大 · 影响:`高/中/低`

---

## 🎯 如果只做 3 件事

1. ~~接口层主路径 + 全局去重(#2 #3)~~ ✅ **已做(2026-07-06)** —— 推荐(`rec/geek/list`)+ 搜索(`geeks.json`)双通道都走接口主路径(解决虚拟滚动退化、搜索还免掉了清默认坑),去重用接口自带 `haveChatted`/`friendRelationStatus`。**这道基建门槛跨过了——从演示级迈到生产级的关键一步。** 只剩会话列表是 WebSocket(无干净 REST,回执走 DOM 漏斗)。
2. ~~当日反馈环 + 定制打招呼语(#9 #8)~~ ✅ **三件运营智能层已实现(2026-07-06,playbook §11,默认关)** —— 定制招呼语 + 反馈环 + 薪资破格都落进 skill 了,开 `enabled` 即生效。这层是"智能感"的来源:会看回复率调策略、会按背景写文案、会给破格加薪建议。
3. **参数化浏览器 ID + SAFETY.md + CONTRIBUTING.md(#1 #15 #16)** —— 开源采纳最小三件套:setup 不卡壳、风险讲清楚、社区知道怎么帮修选择器。没这三样,再好的引擎也只有作者一个人在用。

---

## 【代码 / 工程层面】

### P0 — 高杠杆,先做

**#1 参数化浏览器 ID + `verify-setup` 自检** · `S / 高`
全文剩余硬编码 `direct_local_...` 换 `<YOUR_BROWSER_ID>`;SKILL.md「用前必做」补一段复制即跑的 Bash,校验 浏览器 ID / 登录 / 每日额度,输出 pass/fail。跨机交接第一个卡点。

**#2 接口层升为推荐+搜索主路径,DOM 降 fallback** · `M / 高` · ✅ **推荐+搜索通道均已做(2026-07-06)**
- **推荐**:`GET /wapi/zpjob/rec/geek/list?jobId={encJobId}&page=N&{filters}` → `geekList[]`(15/页)+`hasMore`,`geekCard` 全字段 → **虚拟滚动索引退化消失、精确翻页不漏人**。
- **搜索**:`GET /wapi/zpitem/web/boss/search/geeks.json?page=N&jobId={encJobId}&keywords={词}&{filters}` → `geeks[]`(打码人)+`hasMore` → **接口直接传干净 keywords+筛选,免掉了 DOM 路径"清默认预选"那套坑**;去重用 `friendRelationStatus`。
- playbook Step 1/5 已改接口主路径、DOM 兜底;见 operation-map §7e。
> 剩余(未做):**会话/消息列表 = WebSocket**,无干净 REST(`message/list/box` 只是通知盒摘要),回执/会话类去重走 DOM 漏斗或接口的 `haveChatted`/`friendRelationStatus` 标即可。

**#3 全局去重** · `S–M / 高` · ✅ **已做(2026-07-06)**
比预期更好:推荐接口每个候选人自带 **`haveChatted`/`isFriend`**(Boss 官方"已聊过/已好友"标)→ `haveChatted==1` 直接 skip,最准;接口没给的(搜索打码/inbound)走账本交叉比对(`name+公司+期望` 键,打码名↔真名标 `possible_dup`);加 `last_touched_date` 防 24h 重复触达。见 operation-map §7f + playbook Step 3。堵住了重复打招呼这个风控 silent killer。

### P1

**#4 抽 operation-map 内嵌 JS 片段为脚本库** · `M / 中` · ⏸ **可缓(降级为参考附录)**
校准后:skill 是文档+agent 现读现用,不 import 库,所以"抽成 `lib/`"帮助有限。真要做就整理成 operation-map 的"常用 eval 片段"参考附录(带重试/超时约定),低优先。

**#5 strategy.yaml / ledger.jsonl 加 JSON Schema + 启动校验** · ✅ **已做(2026-07-06)**
`schemas/strategy.schema.json` + `schemas/ledger.schema.json`(正式规格)+ **`validate.py`**(自带,只依赖 PyYAML、不需 jsonschema)。跑前 `python3 validate.py strategies/<name>/` 就报"缺 rubric.must / touch_policy 拼错 / 开 salary_leverage 没给 base_salary_range"这类具体错;接进 playbook Step 0。

**#6 run_id 检查点 + 断点续跑** · `M / 中` · ⏸ **可缓(等心跳阶段三)**
现在是单次+手动,续跑需求不强;做阶段三 launchd 心跳(长流程自动多轮)时它才刚需,那时一起做。

### P2

**#7 抽象浏览器交互层(IBrowserDriver)** · `L / 低` · ⛔ **暂不做**
这条假设有个"代码层"可抽象,但现实是 agent 直接调 browser-act CLI、没有那层。工作量 L、收益低,为"以后可能换 Playwright"投这么多不划算。真要换后端那天再说。

**#18 后端可替代性调研** · `S / 中` · ✅ **已做(2026-07-06)**
真机验证了 Playwright 扩展 / chrome-devtools-mcp / claude-in-chrome 等免费开源替代:能力对等、绕开 Chrome 136+ 端口封锁,但装配摩擦不比 browser-act 低。能力契约 + 动词映射 + 实测坑落进 [`BACKENDS.md`](BACKENDS.md)。要换后端照它走。

---

## 【功能 / 产品层面】—— "从会点按钮到懂招聘"

> 共性痛点:strategy.yaml 全是死值,打招呼一律系统模板,agent 对市场/反馈/成本全盲。

### P0 — ✅ 三件已实现进 skill(2026-07-06,playbook §11 + strategy.yaml `intelligence:` 块,默认全关,开 `enabled` 即生效)

> 设计+落地方案见 playbook §11(运营智能层)。三把 `enabled` 独立开关默认 `false`;建议上线顺序 ①反馈环 → ②招呼语 → ③薪资(先装仪表盘、再优化油门、最后改发动机)。**红线守死:能自动的只有"读和算"+疑似风控自动止损;发文案/改预算/破格加薪一律用户点头。**

**#8 分档 / context-aware 定制打招呼语** · ✅ **已实现(§11.1)** —— `intelligence.custom_greetings`;A 档 LLM 按 must_hit/背景生成 ≤30 字、必引具体技能;每条给用户 Y/N/编辑确认才发(红线);打招呼后补发定制句;ledger.actions 记 greeting_mode/text/rationale 审计。

**#9 当日反馈环 + 动态预算建议** · ✅ **已实现(§11.2,新增 Step 6.5)** —— `intelligence.feedback`;聚合 `daily_stats.jsonl` 算回复率对比基线,诊断文案/人群/风控;连续 5 无回复自动暂停止损(唯一自动写);预算/词只出建议不自动改。

**#10 薪资权衡框架(稀缺度 × 预算弹性)** · ✅ **已实现(§11.3,改写 §4 rule 4)** —— `intelligence.salary_leverage` + `budget.base_salary_range/salary_flexibility_pct`;超带候选评 `scarcity_score`,够稀缺标 `A*_salary_sensitive` + 给定量加薪建议;破格永远用户勾同意下轮才触达。

### P1

**#11 掩码候选人花卡前质量预判** · ✅ **已做(2026-07-06,§11.4)**
`intelligence.card_prescreen`(默认开,只减花卡零外发):搜索开卡前用接口免费的 公司/城市/学历/年龄+优势词 四信号打质量分,≥`min_score`(默认6)才建议开卡、3-6 报告待定、<3 不开。接进 playbook Step 5。3卡/次的真金白银用在刀刃上,实测减 20-30% 无效卡。

**#12 约面流程文档化 + offer/入职跟踪** · `M / 中`
live 实测会话内 `.interview` 发起流程写回 operation-map(唯一没跑的核心动作,§8 第④项);ledger 加 `interview_proposed / offer_issued / onboarded`;报告加「待约面」。补上"约面→onboard"才是闭环、ROI 分析才有数据。**约面仍属红线不自动,只文档化 + 报告建议 + 人来点。**

### P2

**#13 多岗多策略并行 + 共享账本** · ✅ **已做(2026-07-06,§12)**
`shared_ledger` + 候选人 `touched_jobs[] / status_global`;跨岗去重(§3 Step 3 ④:任一岗 24h 内触达过就 skip)+ 报告「交叉岗位发现」(A 岗拒→命中 B 岗 rubric→转推)。schema 已含字段。单次单岗非必需,做团队/多岗持续招聘时开。

**#14 平台适配层(拉勾/智联)** · `M / 高` · ⛔ **暂不做**
除非你有拉勾/智联的招聘账号且真想扩,否则跳过——它要对着别的平台真机重抓一整套选择器/接口(≈再做一遍 Boss 的量),当前价值全在 Boss。先把 Boss 做深,别摊大。

---

## 【开源就绪度】

> 现状:操作层再好,陌生人也进不来——需要把风险、贡献方式、故障排查讲清楚。(SAFETY.md / CONTRIBUTING.md 见本仓库同名文件。)

**#15 SAFETY.md** · `M / 高` —— 永久红线(含畅聊卡开聊捆绑 PII 大坑)/ 风控信号与停机判断 / 数据保护(ledger 含 PII 勿上传)/ 共享 Chrome 冲突。✅ 已随本次提交。

**#16 CONTRIBUTING.md** · `M / 高` —— 选择器改版失效的诊断步骤 + 贡献指引 + PR/issue 模板;明确"贡献主要形式 = 反馈改版失效点 + 提供新选择器"。✅ 已随本次提交。

**#17 README 补 FAQ + 演示 GIF + 国际化标注** · ✅ **FAQ 已做(2026-07-06)** —— README 加了 10 条 FAQ(换id / 登出扫码恢复 / 选择器报错 / 3卡在哪 / 求简历灰 / linked_job / yaml校验 / 多agent冲突 / 230404 / 智能层怎么开)。剩:GitHub description/topics 标"中文 only"、demo GIF/截图(要真机录+脱敏,缓)。
