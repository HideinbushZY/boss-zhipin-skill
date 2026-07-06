# Roadmap — boss-zhipin

> 后续改进建议,分**代码/工程层面**与**功能/产品层面**,按优先级(影响高 + 工作量小者靠前)。每条可直接开成一个 issue。
>
> **一句话定位**:操作层已实战淬炼、自洽。现在卡在两道坎——工程上"代码形态的东西还散在 markdown 里",产品上"会点按钮但还不懂招聘"。下一步最该使劲:把 DOM 遍历换成**接口主路径**(救可靠性),同时补**开源就绪度**(救采纳率)。
>
> 工作量:`S`=小 / `M`=中 / `L`=大 · 影响:`高/中/低`

---

## 🎯 如果只做 3 件事

1. ~~接口层主路径 + 全局去重(#2 #3)~~ ✅ **已做(2026-07-06)** —— 推荐(`rec/geek/list`)+ 搜索(`geeks.json`)双通道都走接口主路径(解决虚拟滚动退化、搜索还免掉了清默认坑),去重用接口自带 `haveChatted`/`friendRelationStatus`。**这道基建门槛跨过了——从演示级迈到生产级的关键一步。** 只剩会话列表是 WebSocket(无干净 REST,回执走 DOM 漏斗)。
2. **当日反馈环 + 定制打招呼语(#9 #8)** —— 最高性价比的"智能感":会看回复率调策略、会按背景写文案。用户第一次感到"它在思考",回复率数据翻倍。
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

**#4 抽 operation-map 内嵌 JS 片段为脚本库** · `M / 中`
15+ 个 eval 片段(读 DOM / 清默认 / 扫回执 / 健康检查 / 确认框)抽进 `lib/`(selectors / health-check / cleanup / receipt-scan),参数化 + 返回 `Result<T>` + 重试 + 5s timeout。改版时一眼看出哪块坏、可 mock 单测、跨 skill 复用。

**#5 strategy.yaml / ledger.jsonl 加 JSON Schema + 启动校验** · `S / 中`
`schemas/*.json` + `validate` 脚本(如 ajv),启动前就报"缺 hard_filters.city"这种具体错,而非跑一半 `linked_job undefined`;IDE 补全 tier/status/action 枚举;给贡献者清晰 format guide。

**#6 run_id 检查点 + 断点续跑** · `M / 中`
每 Step 写"step N completed"marker,启动时检测未完成轮次询问 continue/restart,ledger 加 `run_history[]` 追踪链。支持长流程容错(心跳、多轮续跑)。

### P2

**#7 抽象浏览器交互层(IBrowserDriver)** · `L / 低`
定义 `click/input/eval/getState` 接口,实现 BrowserActAdapter / PlaywrightAdapter,业务逻辑走 `adapter.*`。长期独立于 browser-act + mock 完全离线测。

---

## 【功能 / 产品层面】—— "从会点按钮到懂招聘"

> 共性痛点:strategy.yaml 全是死值,打招呼一律系统模板,agent 对市场/反馈/成本全盲。

### P0

**#8 分档 / context-aware 定制打招呼语** · `M / 高`
strategy.yaml 加 `custom_greetings: {default, by_tier, by_target_company}`;playbook 触达环节让 LLM 按 `must.hit / nice.hit / target_company / 期望薪资 / 公司` 为每个 A 档生成 ≤30 字定制语(命中目标公司→"在 X 做 XXX 我们也在研究,想聊聊";全 must→"你的 X 背景很对口…"),发什么写进 ledger.actions 审计;接上 §7d 已记的自定义打招呼语页面。个性化 vs 通用模板,A 级回复率约 30%→60-70%。

**#9 当日反馈环 + 动态预算重分配** · `M / 高`
playbook 加 Step 6.5:算已读率/回复率对比基线,低于基线 −20% 就提示"文案/人群/风控"三选一 + 收缩预算;畅聊卡按"是否转简历/面试"算有效成本;"5 连无回复 → 疑似风控停手冷却";ledger 加 `daily_stats`。从"傻转盘"升"自适应系统"。

**#10 薪资权衡框架(稀缺度 × 预算弹性)** · `M / 高`
strategy.yaml 加 `budget: {base_salary_range, flexibility}`;must 全中但超带 ≤ flexibility 的人标 `A*_salary_sensitive`,报告给"建议破格 +N K"的**定量**建议;A 档不足且超预算时自动出加薪建议。现 §4 rule 4 超带一刀切封顶 B 太糙。

### P1

**#11 掩码候选人花卡前质量预判** · `S / 中`
读 公司/城市/学历/年龄 四信号打"质量分",≥7 直接开、3-6 需预判、低分不建议开卡;ledger 记分反哺门槛。搜索畅聊卡 3 卡/次且捆绑 PII,实测可减 20-30% 无效卡。

**#12 约面流程文档化 + offer/入职跟踪** · `M / 中`
live 实测会话内 `.interview` 发起流程写回 operation-map(唯一没跑的核心动作,§8 第④项);ledger 加 `interview_proposed / offer_issued / onboarded`;报告加「待约面」。补上"约面→onboard"才是闭环、ROI 分析才有数据。**约面仍属红线不自动,只文档化 + 报告建议 + 人来点。**

### P2

**#13 多岗多策略并行 + 共享账本** · `L / 高`
ledger 升 shared,加 `touched_jobs[] / status_global`,多策略同 ledger,报告「交叉岗位发现」(A 岗拒→转推 B 岗)。团队候选池重叠 30-50%,不去重同一人被打好几遍。

**#14 平台适配层(拉勾/智联)** · `M / 高`
短期先 `platform.config.yaml` + operation-map 拆"通用逻辑 / Boss 选择器"两层;长期抽象 recruiter-platform 接口。现在只投分层注释,后续复用成本大降。

---

## 【开源就绪度】

> 现状:操作层再好,陌生人也进不来——需要把风险、贡献方式、故障排查讲清楚。(SAFETY.md / CONTRIBUTING.md 见本仓库同名文件。)

**#15 SAFETY.md** · `M / 高` —— 永久红线(含畅聊卡开聊捆绑 PII 大坑)/ 风控信号与停机判断 / 数据保护(ledger 含 PII 勿上传)/ 共享 Chrome 冲突。✅ 已随本次提交。

**#16 CONTRIBUTING.md** · `M / 高` —— 选择器改版失效的诊断步骤 + 贡献指引 + PR/issue 模板;明确"贡献主要形式 = 反馈改版失效点 + 提供新选择器"。✅ 已随本次提交。

**#17 README 补 FAQ + 演示 GIF + 国际化标注** · `M / 中` —— GitHub description/topics 标"Boss直聘 zhipin.com·中文 only";FAQ 8-10 条(id 怎么换 / 登出扫码恢复 / 选择器报错 / 3 卡在哪看 / 多 agent 冲突 / linked_job 配错 / yaml 语法);推荐卡+搜索+确认框截图 + 5-10s demo GIF(数据脱敏)。
