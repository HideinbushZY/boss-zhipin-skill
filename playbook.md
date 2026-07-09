# boss-zhipin 寻访引擎 playbook(策略驱动)

> 本文件是**编排层/大脑**:把用户的自然语言搜索策略,变成"判定→找人→筛人→触达→反馈"的一轮闭环。
> 执行层(怎么点页面)看 `operation-map.md`;本文只讲**做什么、按什么顺序、什么条件下做**。
> 现阶段范围:**单次 + 手动触发**(心跳留白,§2)。触达默认档 `full`,畅聊卡可用。
> 需要的工具:`Bash(browser-act:*)`(驱动浏览器)+ `Read/Write/Edit`(读写 strategy.yaml / ledger.jsonl / reports)。

---

## 0. 调用契约

- **输入**:① 一段自然语言搜索策略,或 ② 已有 strategy 名(`strategies/<name>/`)。
- **首次拿到策略**:解析成 `strategies/<name>/strategy.yaml`(§1),用 Write 落盘;把解析结果**写进本轮报告开头回显**(全权限模式下不阻塞等确认,但让用户事后看到"我把你的话理解成了什么、替你默认了什么")。
- **可行性预检**(§1.5):跑管线前先判"这策略现在跑得通吗",跑不通就说清并给最优降级。
- **输出**:一份轮次报告 + 更新 `ledger.jsonl`。
- **结束**:`browser-act session close <名>`。

---

## 1. 策略解析(自然语言 → strategy.yaml)+ 解析规则

抽取字段,缺失按默认填并在报告标注。**文件写到 `strategies/<name>/strategy.yaml`**(name = 岗位/主题的 kebab 名)。

| 字段 | 从哪来 | 规则 |
|---|---|---|
| `name` | 主题起 kebab 名 | 也是文件夹名 |
| `linked_job` | 用户给的在线职位标题 | 推荐通道必需;缺失走 §1.5 预检 |
| `hard_filters.city` | 明说的城市 | **必填**;搜索时须显式设(防默认预选污染) |
| `hard_filters.degree/experience` | JD 硬性要求 | 见下【解析规则 2/3】 |
| `keywords[][]` | 技能词/能力 | 见【规则 4】关键词矩阵 |
| `target_companies[]` | "从这几家挖" | **只进 company_bonus,不重复进 nice**【规则 5】 |
| `rubric.must/nice/reject` | JD 硬性/优先/排除 | 见【规则 1/6】 |
| `touch_policy` | 用户档 | 默认 `full`;档义 §5 |
| `budget.chat_cards` | 用户畅聊卡授权 | 【规则 7】:用户全局授权过畅聊卡→默认 4;否则默认 0 |
| `budget.greets_per_day` | — | 默认 15 |
| `target_qualified` | "攒N个" | 合格定义见【规则 8】 |
| `mode` | 措辞+供给 | 现只 `once`(§2) |

**解析规则(消除歧义):**
1. **软要求 vs 硬要求**:用户说"优先/加分/最好/月内到岗加分"→ 放 `rubric.nice`,**绝不进 hard_filters**。只有用户明确当门槛的("必须/至少/起")才进 hard_filters。
2. **hard_filters 设最松边界**:硬筛是页面单选,宁松勿紧(松了靠 rubric 排序,紧了直接丢好人)。学历硬筛设"用户明确的最低",偏好放 nice。
3. **开放区间**:"5年以上"→ experience 下限=5、上限=不限(**别自造上限**,防丢资深)。
4. **关键词矩阵**:3-5 组,每组=一个概念簇(2-4 个近义/同类词),组间轮换(每轮换一组扩覆盖),组内是"或"关系的替代词。从 JD 技能词 + 能力描述的同义/上下位展开。
5. **目标公司不重复计分**:target_companies 只经 §4 company_bonus 加分;**不要**再塞进 rubric.nice(否则同一事实双重加分)。
6. **reject 不臆造**:用户没给排除条件就留空;只在 city 是硬条件时自动加"期望城市完全不符且不接受 relocate"。别替用户发明淘汰规则。
7. **chat_cards 默认随授权 + 🔴PII捆绑机检闸**:用户全局授权过畅聊卡→新策略默认 `chat_cards: 4`;没授权过→默认 0。**"授权过"的机检定义 = `budget.authorize_card_pii_bundle: true`**(不是靠 agent 记忆判断)。**`chat_cards>0` 却没设这个 true → validate.py 直接报错拦下**;因为开聊会自动索要简历/微信/电话(PII 捆绑),必须用户显式知情授权,不能靠文档纪律。
8. **合格(qualified)定义**:默认 `qualified_tiers: [A]`(A 档=达标且现在可触达)。`target_qualified` 用户未明说时**默认 10**;A 档累计达 target_qualified 即这个策略够了。`A*`(破格)不计入默认合格数,除非策略显式纳入(§4)。

---

## 1.5 可行性预检(跑管线前的自检——修复"结构性死锁")

解析后、跑管线前,先回答:**这策略现在有没有"能找人的通道"和"能触达的手段"?**

**A. 通道可用性**
- `linked_job` 有 → 推荐通道可用(免费打招呼)。
- `linked_job` 缺 → 先 `browser-act` 到职位管理列出在线职位,**按标题/类目自动匹配一个最贴近的已发布职位并 link**;
  - 匹配到 → 写回 strategy.yaml 的 linked_job,推荐通道启用。
  - 没有匹配 → **推荐通道禁用**。报告明说"无对应在线职位→免费推荐通道不可用,建议你发布一个 XX 职位以启用",本轮只走搜索通道。**绝不自动发布职位**(§5 红线)。

**B. 触达手段 × 预算 交叉校验(修复 full×0卡×搜索死锁)**
- 若 `touch_policy` 是打招呼档(greet_*/full),检查"A 档候选人会从哪个通道来、那个通道触达要不要卡":
  - 有免费推荐通道 → 免费打招呼,OK。
  - 只有搜索通道 且 `chat_cards=0` → **触达会全程哑火**。处理:
    - 本策略已显式授权(机检定义 = `budget.authorize_card_pii_bundle: true`,§1 规则7;别靠记忆或别的策略的授权推断)→ 自动把 chat_cards 设为 min(合理上限, 需求),报告记账并说明。
    - 没授权 → **本轮降级为 report_first**(只出名单),报告醒目提示"full 触达在无免费通道+0卡下无法执行,已降级;要触达请设 chat_cards>0 或发布职位启用推荐"。
- 把预检结论写进报告开头("本轮可用通道:推荐✓/搜索✓;触达:free推荐 + 畅聊卡≤4")。

---

## 2. 模式判定(once vs heartbeat)

**现只实现 `once` + 手动触发。** 心跳(launchd)是阶段三,预留判定不自动起。

| 信号 | → once | → heartbeat |
|---|---|---|
| 策略性质 | 摸底/定向名单 | 在招岗位持续补人 |
| 首轮供给 | 合格充足一轮够 | 稀缺需守候 |
| 用户措辞 | "看看/给个名单" | "帮我盯着/持续找" |

判定+理由写进报告;偏 heartbeat 的给建议("建议转心跳,但需你机器常开;当前只能 once")。`schedule.stop_when` 在 once 下为死配置,忽略即可。

---

## 3. 单轮寻访管线(把免费杠杆用到极致)

```
Step 0  健康检查  [operation-map §7d 健康检查读法,选择器已验证]
  · **跑前校验**:`python3 validate.py strategies/<name>/` —— 过了再跑,把"缺 rubric.must / touch_policy 拼错 / 开 salary_leverage 没给 base_salary_range"这类配置错挡在早期(schema 见 schemas/,校验器不依赖 jsonschema)
  · 登录:eval .user-name 有值(⚠ 浏览器 id 用你自己的,SKILL.md §用前必做)
  · 每日打招呼额度:**接口优先(2026-07-07)**——`privilege/my/detail` 每日沟通总量(200) − `recruitDataCenter/get.json` 的 `todayData.chatInitiative`(今日已打招呼)= 剩余(见 operation-map §7d);DOM 兜底=读 data-recruit 的「沟通 X/200」。剩余<~10 就收/停,别撞上限触软风控
  · 畅聊卡余量:**接口** `geeks.json` 顶层 `chatCardCount`(operation-map §7d/§7i);单次开聊成本逐人 1~3 张(读 `searchChatCardCostCount`),预算按每人实际消耗折算,别按固定 3
  · 风控体感:聊天页反复"加载中"/额度异常/动作被拒 → 疑似软风控,停手冷却
  → 任一不足(未登录/额度剩<本轮预算/疑似风控)→ 停,报告

Step 0.5  扫回执(补全 full 档异步闭环)  [operation-map §4.7 geekListV2 主路径 / §7c DOM 兜底]
  · **取名单=接口优先(2026-07-07 起)**:同源 sync-XHR 调 `GET /wapi/zprelation/friend/manage/geekListV2?workflow=沟通中&page=N&pageSize=15` → `zpData.result[]`(每人 name+securityId+lastMsg/lastTS+encryptJobId),按 lastTS 判谁刚回;比翻 DOM 漏斗干净(§4.7)。要看某漏斗态全量就换 `workflow={单聊|沟通中|已约面|…}`。
  · DOM 兜底:进沟通页(左菜单点「沟通」,别冷加载 URL)→ 点「沟通中」漏斗 tab(div[title=沟通中])→ 取活跃对话名单
  · 与 ledger 里 status∈{greeted,chatted} 的人取交集 = 本轮"回复了、求简历已解锁"的人
  · 对交集每人:打开会话后先核收件人(.name-container .name-box = 该人名,三验①)再点「求简历」——求简历也是外发,发错人同样不可撤回
  · 对交集每人(full/greet 档):开会话 → 点「求简历」(此时 enabled)→ 确认框「确定向牛人索取简历吗?」→ 确定 → ledger 记 request_resume;换电话/微信仍红线不自动
  · 没交集就跳过(说明还没人回);inbound 天然"没status"不算回复,别误判

Step 1  推荐通道(免费,优先)   [operation-map §7e 接口主路径 / §2A DOM 兜底]  —— 仅当 §1.5 预检 linked_job 可用
  · **主路径=接口(2026-07-06 起)**:拿 linked_job 的 encJobId(抓包 rec/geek/list 的 jobId,或从推荐 iframe 取),同源 sync-XHR 调
    `GET /wapi/zpjob/rec/geek/list?jobId={encJobId}&page=N&{age/degree/experience/salary 映射 hard_filters}` →
    逐页拉(每页15)直到 `hasMore=false`,从 `geekList[].geekCard` 直接拿 name(**真名**)/securityId/经验/学历/优势/期望薪资/城市/教育/工作经历 —— **无虚拟滚动、无 state 索引退化**。
    · **⚠ 一趟扫完,别中途回 page1**(2026-07-08 实测,§7j):推荐池**每次重新拉 page1 会重排**(连拉两次首屏全不同),但**一趟连续 1→N 是连贯的**(8页120条、去重0重复)。→ 枚举整池必须一口气 page 1→N 走完;要重扫就整趟重来,别夹在中间刷新。
  · **DOM 兜底**:接口 401/网络错/字段变 → 降级回 §2A 的 DOM 扫卡(推荐/精选/最新 tab)。DOM 只用于"开详情弹 + 点打招呼按钮"这类交互,不再靠它遍历列表。

Step 2  互动通道(免费)        [operation-map §4.6]
  · "对我感兴趣"/"同事推荐";⚠ 互动是账号全局非按岗位 → 只取"沟通职位"= 本策略 linked_job 的人(operation-map §4.6)

Step 3  全局去重              [§6 / operation-map §7f]
  · ledger 不存在则先 Write 建空文件
  · **① 接口内建标(推荐通道首选)**:`geekList[].haveChatted==1` 或 `isFriend==1` → 已接触,直接 skip、别再触达(Boss 官方口径,最准)。
  · **② 账本交叉比对**:接口没给 haveChatted 的人(搜索打码/inbound),用去重键 `(name或打码名前缀)+最近公司+期望` 比对 ledger 里已触达状态的人;相似即判重复,打码名↔真名标 `possible_dup` 人工确认,不静默双跑(省额度/卡)。
  · **③ 防重复触达**:同一人 24h 内已触达就跳过(ledger `last_touched_date`)——重复 pitch 是风控 silent killer。
  · **④ 跨岗去重(若开 shared_ledger)**:查全局 `touched_jobs`,同一人被任一岗 24h 内触达过 → 本岗 skip/降优先级;C/拒 但命中本岗 rubric 的转"交叉岗位发现"(§12)。

Step 4  LLM 打分              [§4]

Step 5  搜索通道(补量)       [operation-map §7e 接口主路径 / §2B DOM 兜底]  —— 仅当 A 档不足 target_qualified
  · **主路径=接口(2026-07-06 起)**:同源 sync-XHR 调
    `GET /wapi/zpitem/web/boss/search/geeks.json?page=N&jobId={encJobId}&keywords={关键词}&city={cityCode}&experience={min,max}&salary={min,max}&age={min,max}&degree={code}&source=1` →
    从 `zpData.geeks[]`(打码人)逐页拉到 `hasMore=false`。**接口直接传干净 keywords+筛选,免掉了 DOM 路径"清默认预选"那一套坑**;关键词矩阵在 keywords 里逐组轮换。
  · **详情也走接口(2026-07-07 起):** 要深读某打码候选人的全文简历(工作职责/项目/教育)→ 拿该人 `geeks.json` 响应里的 `geekCard.securityId` 调
    `GET /wapi/zpitem/web/boss/search/geek/info?securityId={securityId}&query={关键词}&encryptGeekDetailGray=1` → `zpData.geekDetail` 是**明文结构化简历**(§7e)。**免费、零外发**。⚠ 别靠 DOM 点结果卡读详情——那是新标签+canvas 反爬,读不到(§2B)。
  · **DOM 兜底**:仅接口异常时才降级 §2B DOM 搜索(清默认预选 + searchFrame);DOM 只在"真开聊触达"时碰。
  · 去重:`geeks.json` 的 `friendRelationStatus`/`geekCallStatus` 命中即已联系过,skip(§7f)。
  · 〔card_prescreen,默认开〕**开卡前先按 §11.4 用免费信号打质量分**,<min_score 不开卡(打码人信号糙,1~3卡/次别冲动);拿不准就先 `geek/info` 免费读全文简历再定,≥门槛才进触达。
  · 浏览列表免费;**触达打码人要开聊、耗畅聊卡**(逐人1~3卡/次,读searchChatCardCostCount,+捆绑索要简历/微信/电话PII)。**前置闸:开聊前确认 `budget.authorize_card_pii_bundle==true`**(Step 0 的 validate.py 已强制:没这个 true 且 chat_cards>0 直接拦下);→ Step 6 按 budget.chat_cards 逐张记账、超停。开聊走 UI(有确认框/境外提示门)。

Step 6  触达(按 touch_policy)  [§5 / operation-map §7j 推荐扫池群发]
  · **主引擎=推荐通道"扫池群发"(免费、可靠,§7j)**:对 Step1 枚举出的推荐池、经 Step3 去重(haveChatted/isFriend==0)+ Step4 打分达标的人,逐个在 recommendFrame 卡上点 `button.btn-greet`(**一键、无确认弹层**,发系统模板"你好,我司急聘{岗位}一职,请问考虑么?",走标准额度**不扣卡**)。**无批量端点 → 逐卡循环点**;每个之间留间隔。
  · **额度闸**:日限 200 沟通,开跑前算 `剩余=200−todayData.chatInitiative`(§7d);逐个记数,到剩余=0 停,别硬闯。
  · **走量 vs 定点**:本步(推荐扫池群发)是**走量**;要**定点触达某几个指定的人**,走搜索定点法(清污染 jobId=0 + 该人独特关键词精准置顶 → UI 开聊,operation-map §7i;已开聊者自动从搜索隐藏、不用手动去重)。两者都可自动,别再当"定点做不到"。 **定点开聊执行层踩坑**(接口评估与 UI 触达用同一关键词、当场认人别离线复现清单、选岗控招呼调性+花卡前验 `li.active`、卡摘要会骗需读全简历+强签名核身)见 operation-map §7i-复盘。
  · 搜索来的(打码人)按 budget.chat_cards 逐张记账,超停(耗畅聊卡+PII捆绑,§7i;成本逐人1-3张读 searchChatCardCostCount)
  · 开聊前看"同事沟通进度",不重复 pitch
  · 〔若 intelligence.custom_greetings.enabled〕A 档先按 §11.1 生成定制招呼语 → 用户逐条确认 → 打招呼后补发定制句;否则发系统模板
  · 每个外发动作:写账本 + 计当日额度 + 卡记账;动作间留间隔
  · 🔴 会话内发消息必过"三验":①收件人(聊天头部 .name-container .name-box = 目标名)②内容(编辑框=批准稿)③送达回读(线程仍是目标+末条气泡=刚发内容)——缺一不发(operation-map §7c,真实误发事故换来的)

Step 6.5 反馈评估(仅 intelligence.feedback.enabled)  [§11.2]
  · 数据源=`recruitDataCenter/get.json` 的 `todayData`(接口,§7d:view/chatInitiative/chat/resume… 带较昨日)+ 本地 actions;聚合当日 → 写 daily_stats,算回复率/已读率,对比 baseline(**别爬看板 DOM**)
  · 低于基线 → 诊断(文案/人群/风控);连续无回复≥阈值 → 自动暂停止损(唯一自动写)
  · 预算/词只出建议进报告,不自动改 yaml

Step 7  写账本 + 报告          [§6 §7]
  · 〔若 shared_ledger〕写本策略 ledger 的同时,同步共享账本:该人 touched_jobs 追加 {job,status,date}、刷新 status_global(§12 写入侧闭环——只读不写,下一个策略就查不到本轮触达,跨岗去重失效)
```

---

## 4. 打分引擎(rubric → A/B/C,含优先级规则)

对每个新候选人输出:
```
{ score:0-10, tier, must_hit[], must_miss[], nice_hit[], reject_hit[],
  company_bonus:bool, reachable_now:bool, one_line }
```

**判档规则(优先级从高到低,cap 压过数值):**
1. 命中任一 `reject` → **C(淘汰)**,终止。
2. 数据不足以判 must(简历没开/字段空)→ **tier = `unscored`(待补)**,不塞进 A/B/C;报告单列。
3. 缺任一 `must` → **封顶 B**(数值再高也 B;数值只在 B 内排序)。
   - 若某 must 只能从简历判(如"独立负责")→ 标 `provisional`,状态 `pending_resume`,暂按已知信息给临时档,开简历后重判。
4. `reachable_now = false`(薪资远超带 且 "暂不考虑"/不主动,或城市硬冲突)→ **封顶 B**(A 保留给"现在值得联系且大概率能谈"的人)。
   - **〔若 intelligence.salary_leverage.enabled〕薪资超带这一支改走 §11.3**:不即刻封 B,而是评 `scarcity_score`,够稀缺则标 `A*_salary_sensitive` + 给定量加薪建议(仍零自动触达,等用户授权)。城市/意愿硬冲突仍封 B。
5. 其余按数值:**A ≥ 7.5;B 5 ≤ score < 7.5;C < 5**。nice/company_bonus 加分;薪资/城市/到岗错配 → 每项 −1~2 分并在 one_line 点出。

**tier 取值:`A` / `B` / `C` / `unscored` / `A*`。** `A*` = **破格档**:技能明显 A 级、但被某条 cap 规则(如 <3年经验、略超带)压到 B,经**用户显式授权**破格触达的人。`A*` 不自动产生(不能靠数值升到 A*),只在用户拍板后由触达环节标注;计数上单列(不混入默认 `qualified_tiers:[A]`,除非策略显式把 A* 纳入)。ledger 用 `A*` 记这类候选人。**其中"薪资超带但技能稀缺"这类破格由 §11.3 薪资框架产出、标 `A*_salary_sensitive`。**

`one_line` 必含:最大亮点 + 最大顾虑(薪资/意愿/经验缺口等)。

---

## 5. 触达执行(touch_policy 档义)

| 档 | 自动做 | 报告给 |
|---|---|---|
| `report_first` | 零外发 | A/B/C 全名单+打分 |
| `greet_A_capped` | A 档自动打招呼(额度内,系统语) | B/C |
| `greet_custom` | A 档自动打招呼(自定义语,引用背景)——**实现见 §11.1**(生成→用户逐条确认→打招呼后补发定制句;`intelligence.custom_greetings.enabled` 时任何含 A 打招呼的档都走它) | B/C |
| **`full`(默认)** | A 档自动 打招呼 **+ 回复后求简历** | B/C + A 触达结果 |

**⚠ full 档的"求简历"有平台前置门(2026-07-04 live 实测)**:候选人**未回复**时(会话 `[送达]`,非「沟通中」)求简历按钮是 `operate-btn disabled`,**点不动**。所以 full 档不是"打招呼当下顺手求简历",而是**打招呼 → 候选人回复 → 求简历**两拍。单次模式下,本轮打完招呼、候选人还没回,求简历就标 `pending-reply`,写进报告"待回执",下一轮(或阶段三心跳扫回执)再补。**别用 eval 强点 disabled 按钮**(无效且越红线)。

**永久红线(任何档、任何模式都不自动,只报告建议)**:换电话 / 换微信 / 约面 / **删除职位** / 举报 / 批量标记不合适(均不可逆/深PII)。`budget.chat_cards=0` 时不碰卡。
**关闭/发布职位=可代操作**(非红线):关闭可逆(硬门=核对岗位+确认+验证);发布须提交前回读 4 个锁死字段+内容给用户确认、发布后弹的付费曝光只关不买(见 operation-map §4.1/§4.2/§6)。删除仍是唯一红线。
**限速冷却**:动作间留间隔;命中疑似风控(卡死/额度异常/提示)立即停、报告、不连续重启 Chrome。

---

## 6. 账本 ledger.jsonl(状态机 = 增量根基)

每候选人一行 JSON。**首轮若文件不存在先 Write 建空。** 状态机(覆盖账本实际用到的所有 status):
`found`(搜索命中未触达)`→ scored → greeted`(打招呼)`/ chatted`(畅聊卡开聊)`→`〔打招呼/开聊后候选人**未回复**时=`pending-reply` 状态,求简历还发不了,见 §5〕`→ replied`(对方回复、进「沟通中」,求简历解锁)`→ resume_requested`(已点求简历、等对方发)`→ resume_received → contact_exchanged → interview → hired`。（`resume_requested` 是 validate.py/schema 认的合法态,别漏用）
旁路:`unfit`(命中 reject / C 淘汰)`/ no_reply / unscored`(数据不足待补)`/ inbound_msg`(对方主动来招呼、待处理)。

**去重键**:优先稳定 id;否则 `(name 或打码名前缀) + 最近公司 + 期望`多信号比对。**打码名(搜索)↔真名(推荐)可能是同一人**→ 命中相似即标 `possible_dup` 人工确认,不静默双跑(省额度/卡)。

字段:`id/name/masked/source/job/score/tier/status/first_seen/last_action/expect/company/actions[]/notes`。actions 记 `{t, act, cost(free|畅聊卡xN), result}`,可累加审计卡与额度。

**运营智能层新增字段(仅对应 enabled 时写,见 §11):**
- 候选人级(薪资框架):`salary_gap`(期望下限−base_max,K)、`scarcity_score`(0-10 纯技能稀缺)、`recommend_salary_delta`(建议加薪 K)、`salary_flexible_tier`(A*_salary_sensitive|null)、`approved_ceiling`(用户授权上限|null)、`last_touched_date`(防 24h 重复触达)。
- `actions[]` 内(定制招呼语):`greeting_mode`(custom|default)、`greeting_text`、`greeting_length`、`greeting_rationale`。
- **策略级 `daily_stats.jsonl`(反馈环,单独文件,不塞候选人行)**:每天一行 `{date, greets, delivered, reads, replies, cards_used, chat_converted, reply_rate, read_rate, diagnosis, no_reply_streak, status_flag}`。跨日累计 `no_reply_streak` 驱动风控判定;数据只从 actions 时间戳 + 扫回执聚合(无新 API)。

---

## 7. 报告(每轮一份,落 `strategies/<name>/reports/`)

**轮次号**:= 该 strategy 下已有 report 数 + 1(离线验证记 round-0)。文件 `round-<N>-<YYYYMMDD-HHMM>.md`。

格式:
```
【<name> 寻访 · 第N轮 · <时间> · 模式:once】
可行性预检:可用通道(推荐?/搜索?)· 触达手段(free/卡≤?)
策略回显:linked_job / city / 关键词组 / rubric摘要 / 触达档 / budget · 替你默认了什么
本轮:推荐X / 互动Y / 去重后新Z → A? B? C? unscored?
A 档(合格,建议/已联系):姓名|公司·职位|背景|匹配N.N|一句结论(亮点+顾虑)|触达[已招呼/已求简历/未发]卡[free|xN]
B 档:简列(含缺 must/reachable 原因)
C 档:数量+主因
unscored:数量+缺什么数据
账本:累计合格(A)P/目标Q。畅聊卡余R(本轮用S)。今日打招呼U/上限。
〔若 salary_leverage.enabled〕【破格候选】姓名|超带{gap}K|稀缺度{score}/10|建议加薪至{X}K→可达性|**需你勾同意才下轮触达**
〔若 feedback.enabled〕【当日反馈评估】回复率{r}(基线{b})/已读率|诊断:{文案|人群|风控|观察}|预算建议:greets {旧}→{新建议}(不自动改)|{疑似风控已自动暂停?}
风险/异常 · 建议下一步(继续/转心跳/调策略/需人工点的深动作)
```

---

## 8. 预算与安全护栏

- `greets_per_day` 默认 15(账号总额通常 200/天)。
- `chat_cards`:默认随授权(§1 规则7);逐张记账、超停。
- `detail_views_per_run` 默认 40。
- 动作间隔;命中疑似风控立即停;不连续重启 Chrome(会登出,需用户手机)。**账号=公司资产,宁慢勿封。**

---

## 9. 与 operation-map 分工

playbook = 判定/调度/打分/触达策略/账本/报告(想什么、按序做);operation-map = 页面怎么点(URL/选择器/确认框/坑)。四条铁律(读用 eval、点用索引;聊天页走菜单;搜索页先清默认;发消息前必核收件人)总纲在 SKILL.md,细则分见 operation-map §0/§7c/§2B,执行必守。

---

## 10. 已知限制(需 live 验证补选择器)

这些是执行层待补,遇到时优雅降级、别硬撞:
- ~~搜索页默认预选清除选择器~~ **✅ 2026-07-05 已验证补齐**(关键词/职位/城市三件套,见 operation-map §2B;城市默认空不污染)。
- ~~Step 0 健康指标无选择器~~ **✅ 2026-07-05 已验证**(每日打招呼额度=data-recruit iframe「沟通 X/200」、畅聊卡余量=geeks.json 顶层 chatCardCount 接口,见 operation-map §7d/§7i)。
- ~~full 档求简历异步闭环~~ **✅ 2026-07-05 已定义扫回执**(沟通中 tab ∩ ledger greeted/chatted → 求简历,见 Step 0.5 + operation-map §7c)。
- **约面(`.interview`)发起流程仍未实测**(用户暂缓;红线不自动,但操作本身待文档化)。
- **接口层**:推荐 `rec/geek/list` + 搜索 `geeks.json` 已作主路径(operation-map §7e);**互动 `interaction/bossGetGeek`(§4.6)+ 牛人管理漏斗 `friend/manage/geekListV2?workflow=`(§4.7)也是干净 REST**。**扫回执/查进展优先走 geekListV2(按漏斗态拉名单+lastMsg/lastTS)或推荐接口 haveChatted,DOM 漏斗退为兜底**;只有**逐条消息收发**才是 WebSocket、无 GET REST(§7e🟡)。
- **浏览器 id 非通用**:命令里用 `<YOUR_BROWSER_ID>` 占位,每次先 `browser-act browser list` 换成自己的。

---

## 11. 运营智能层(intelligence,可选;custom_greetings/feedback/salary_leverage 默认关,card_prescreen 默认开)

> ⚠ **本层逻辑经离线真实数据验证、未真机整轮外发实测(见 operation-map §8)**;首次启用按未测能力谨慎跑、盯首轮回执。
> 四个功能把引擎从"会点按钮"升到"懂招聘":薪资框架(§4 打分·产人)→ 定制招呼语(Step 6·发文案)→ 反馈环(Step 6.5·收数据反哺前两者)+ 花卡预判(§11.4·Step 5 开卡闸)。在 strategy.yaml 的 `intelligence:` 块里各有 `enabled` 开关:**前三个默认 `false`,card_prescreen 默认开(只省钱不外发)**;关时管线按老逻辑走,开时才挂载对应逻辑。建议上线顺序:①反馈环 → ②招呼语 → ③薪资(先装仪表盘、再优化油门、最后改发动机)。
>
> **🔴 铁律:能自动的只有"读和算"**——聚合数据、算回复率、评稀缺度、生成招呼语**草稿**、疑似风控时**自动暂停止损**(唯一的自动写动作,方向是"停")。**凡往外走或改策略的都要用户点头**:发招呼语(逐条 Y/N/编辑)、改预算/greets、破格加薪(勾同意下轮才触达)、改搜索词——一律只出建议。

### 11.1 定制招呼语(custom_greetings)— 挂在 Step 6
门槛:`enabled=true` 且 `tier∈tiers` 且该人 `haveChatted==0`(仅首触)。否则用系统模板。
- **生成**:LLM prompt。System 硬约束:① 字数严格 ≤ `max_chars`,越界 `valid=false`;② 只引用候选人真实背景不编造;③ 必须提一个**具体技能/项目名**(不能只"很厉害");④ 提及技能须是当前岗位 must_hit;⑤ 真诚不油腻(禁"非常荣幸"套话)。返回 `{greeting, why, length, valid}`。User prompt 注入:linked_job + must 逐项、候选人 name/company/geekDesc/最近2段经历、匹配信号(must ✓/✗、nice 强/弱、target_company 命中)。任务:"选该人最独特、最对口本岗的一个技能作切入点"。
- **校验+兜底**:`length>max_chars` 或 `valid=false` 或 LLM 5s 超时 → fallback 系统模板,报告注明 fallback 原因。
- **发送门(红线)**:`require_user_confirmation` 恒 true → 每条给用户看确认卡 `【定制招呼语确认】候选人 | 生成文本 | 依据 | 字数N/max | (Y/N/编辑)`;**没点头不发**。Y=发定制、N=发默认、编辑=校验字数后再问。
- **落地**:Boss 的推荐/搜索"打招呼"按钮发的是账号系统模板,不能在点的当下换文案 → **定制那句用"打招呼(触发对话)→ 立刻在会话里补发定制消息"**(会话回复流程见 operation-map §7c:`#boss-chat-editor-input` + `.submit`)。
- **审计**:ledger.actions 记 `greeting_mode(custom|default)/greeting_text/greeting_length/greeting_rationale`。
- 例(某会议前端声学候选人(示例),must✓阵列声学):→ "您的阵列/波束处理经验正是会议系统的核心。"(26字)替代通用"你好,我司急聘…请问考虑么?"。

### 11.2 当日反馈环(feedback)— 新增 Step 6.5(触达后、报告前)
`enabled=true` 才跑,否则跳过。数据源只用 `actions[]` 时间戳 + Step 0.5 扫回执,**无新 API/权限**。
1. 聚合当日 → 写 `daily_stats.jsonl`(见 §6),算 `reply_rate=replies/delivered`、`read_rate=(reads+replies)/delivered`。
2. 对比 `baseline`;`reply_rate − baseline.reply_rate ≤ low_reply_delta(-0.20)` 且样本 `≥ min_samples_for_diagnosis(3)` → 进诊断(样本不足只写"观察更多数据",不判)。
3. LLM 诊断权重:已读未回 >30% → **文案**;A档占比 <30% 且 delivered>5 → **人群**;连续无回复 ≥5 且多候选人 → **风控**;卡转化 <0.15 → 卡ROI。
4. `no_reply_streak ≥ no_reply_streak_stop(5)` → **自动标 `status_flag=paused_suspected_throttle`、停本轮新触达冷却 `cooldown_hours`**(唯一自动止损)。
5. 生成预算建议(新 greets_per_day 值)+ 诊断结论 → **只写进报告【当日反馈评估】,不改 yaml**(改预算/词用户下轮手动)。

### 11.3 薪资破格框架(salary_leverage)— 改写 §4 rule 4
`enabled=true` 才用新逻辑;否则超带即封 B(旧)。打分时(零外发):
- `salary_gap = 候选人期望下限 − budget.base_max`;
- `gap ≤ 0` 带内,正常评分;`0 < gap ≤ base_max×flexibility_pct%` 轻微超带,不降档,标 `recommend_salary_delta=gap`;
- `gap >` 弹性上限 → 严重超带,LLM 评 **`scarcity_score`(0-10,纯技能稀缺,无关薪资/年限)**:must 全中+1、nice 每命中+0.25~0.5、目标公司+1、资历修饰(资深纯血/博士声学/论文专利 +1.5~2.5、纯学术无落地 −2)。
  - `scarcity_score ≥ scarcity_threshold(7.5)` → **`tier='A*_salary_sensitive'`(破格候选,不封 B)**,报告给"建议加薪至 `min(期望下限, base_max×(1+pct%))` 后可达性 high,需授权";
  - `< 7.5` → 仍封顶 B,报告"超带 {gap}K 但稀缺度仅 {score}/10,不自动争取"。
- **拍板门(红线)**:`A*_salary_sensitive` **只报告零自动触达**;`break_glass_mode=manual` 时用户勾同意 + 写 `approved_ceiling` → **下一轮**才落定 A\* 进触达(并复用 §11.1 定制语通道:"…考虑您的背景,薪资可谈至 X…")。改薪资策略/破格承诺永远用户拍板。
- 例(某13年纯血ASR候选人(示例),13年纯血ASR,base 上限 50K、期望下限 60K,即超带 10K):scarcity 8.5 ≥ 7.5 → 破格候选,"建议加薪至 57.5K(弹性上限=50×1.15)或 60K(期望下限),需授权"。

### 11.4 掩码候选人花卡前质量预判(card_prescreen)— 挂在搜索通道触达前(默认开,只省钱不外发)
搜索畅聊卡开聊 = **逐人1~3卡/次(searchChatCardCostCount)+ 捆绑索要 PII**,而搜索结果是打码人、信号纯度低(实测有滥竽充数,如"22年经验投ASR的后端")。花卡前先用**接口免费拿到的四信号**(`geekCard` 里的 公司/城市/学历/年龄 + `friendRelationStatus`)打一个"质量分",别看到打码 A 就冲动开卡。
- **质量分(0-10,粗判是否值得花卡,不是最终 rubric)**:公司对口/知名 +2、城市命中 hard_filters +2、学历达标 +1.5、经验在 3-10 区间 +1.5、优势文案含岗位核心词 +2、`friendRelationStatus`=已联系 → 直接 0(去重)。
- **门槛**(strategy 可配 `intelligence.card_prescreen.min_score`,默认 6):≥6 建议开卡;3-6 报告里列"待定,人工看要不要花卡";<3 不建议开、不进 budget。
- 这一步**纯读接口 + 算分,零外发、零红线**,是把开聊畅聊卡这笔真金白银用在刀刃上。**预计**可减 20-30% 无效卡(离线逻辑验证,§11 未真机整轮实测,见 §8)。
- 默认 `enabled: true`(它只会**减少**花卡,越保护越好;要全量开卡可关)。

---

## 12. 多岗/多策略 共享账本(可选,团队/多岗持续招聘用)

单岗单策略时 ledger 各管各的;但**同一批候选人常横跨多个岗**(团队候选池重叠 30-50%),各管各的会导致**同一人被 A 岗、B 岗分别打招呼**——既浪费额度,又是 24h 重复触达的风控隐患。开启共享账本后:

- **一个共享 ledger**(如 `strategies/_shared/ledger.jsonl`),多策略都往里写,候选人对象加:
  - `touched_jobs[]`:该人被哪些岗触达过(`[{job, status, date}]`);
  - `status_global`:跨岗最新状态(如"A岗已拒/B岗沟通中")。
- **去重升级(§3 Step 3)**:触达前不只查本策略,查**全局** `touched_jobs` —— 同一人 24h 内已被任一岗触达 → 本岗 skip 或降优先级,别重复 pitch。
- **交叉岗位发现(报告新增)**:A 岗打分 C/拒 的人,若技能命中 B 岗 rubric → 报告【交叉岗位发现】"某某 A岗超带但对口你的 B岗,建议转推"。把"一次评估"复用到多个岗,是多岗招聘的增量。
- **落地**:strategy.yaml 加 `shared_ledger: strategies/_shared/ledger.jsonl`(不设=各用各的);id 用 §3 已有的稳定去重键跨策略对齐(打码名↔真名仍标 possible_dup)。**读写两侧都要接**:读侧=§3 Step 3 ④ 查全局 touched_jobs,写侧=§3 Step 7 触达后同步回写(validate.py 会校验 shared_ledger 路径与 touched_jobs/status_global 字段形状)。
- **验收用例**(开启后跑一次):两个策略搜同一家公司的人 → 第二个策略对已触达者应 skip/降级,不重复打招呼。
- 现阶段(单次+单岗)非必需;做团队/多岗持续招聘或阶段三心跳时再开。
