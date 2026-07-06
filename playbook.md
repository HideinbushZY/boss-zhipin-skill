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
7. **chat_cards 默认随授权**:用户全局授权过畅聊卡→新策略默认 `chat_cards: 4`;没授权过→默认 0。
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
    - 用户全局授权过畅聊卡 → 自动把 chat_cards 设为 min(合理上限, 需求),报告记账并说明。
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
  · 登录:eval .user-name 有值(⚠ 浏览器 id 用你自己的,SKILL.md §用前必做)
  · 每日打招呼额度:进 /web/chat/data-recruit,读该页 iframe.innerText 的「沟通 X/200」→ 剩余=200−X;剩余<~10 就收/停,别撞上限触软风控
  · 畅聊卡余量:搜索结果详情右侧「畅聊卡 剩余次数 xN」或按钮「搜索畅聊卡(3/N)」的 N;开聊=3卡/次,预算按 3/开聊 折算
  · 风控体感:聊天页反复"加载中"/额度异常/动作被拒 → 疑似软风控,停手冷却
  → 任一不足(未登录/额度剩<本轮预算/疑似风控)→ 停,报告

Step 0.5  扫回执(补全 full 档异步闭环)  [operation-map §7c 扫回执机制]
  · 进沟通页(左菜单点「沟通」,别冷加载 URL)→ 点「沟通中」漏斗 tab(div[title=沟通中])→ 取活跃对话名单
  · 与 ledger 里 status∈{greeted,chatted} 的人取交集 = 本轮"回复了、求简历已解锁"的人
  · 对交集每人(full/greet 档):开会话 → 点「求简历」(此时 enabled)→ 确认框「确定向牛人索取简历吗?」→ 确定 → ledger 记 request_resume;换电话/微信仍红线不自动
  · 没交集就跳过(说明还没人回);inbound 天然"没status"不算回复,别误判

Step 1  推荐通道(免费,优先)   [operation-map §7e 接口主路径 / §2A DOM 兜底]  —— 仅当 §1.5 预检 linked_job 可用
  · **主路径=接口(2026-07-06 起)**:拿 linked_job 的 encJobId(抓包 rec/geek/list 的 jobId,或从推荐 iframe 取),同源 sync-XHR 调
    `GET /wapi/zpjob/rec/geek/list?jobId={encJobId}&page=N&{age/degree/experience/salary 映射 hard_filters}` →
    逐页拉(每页15)直到 `hasMore=false`,从 `geekList[].geekCard` 直接拿 name/经验/学历/优势/期望薪资/城市/教育/工作经历 —— **无虚拟滚动、无 state 索引退化、可精确翻页不漏人**。
  · **DOM 兜底**:接口 401/网络错/字段变 → 降级回 §2A 的 DOM 扫卡(推荐/精选/最新 tab)。DOM 只用于"开详情弹 + 点打招呼按钮"这类交互,不再靠它遍历列表。

Step 2  互动通道(免费)        [operation-map §4.6]
  · "对我感兴趣"/"同事推荐";⚠ 互动是账号全局非按岗位 → 只取"沟通职位"= 本策略 linked_job 的人(§10)

Step 3  全局去重              [§6 / operation-map §7f]
  · ledger 不存在则先 Write 建空文件
  · **① 接口内建标(推荐通道首选)**:`geekList[].haveChatted==1` 或 `isFriend==1` → 已接触,直接 skip、别再触达(Boss 官方口径,最准)。
  · **② 账本交叉比对**:接口没给 haveChatted 的人(搜索打码/inbound),用去重键 `(name或打码名前缀)+最近公司+期望` 比对 ledger 里已触达状态的人;相似即判重复,打码名↔真名标 `possible_dup` 人工确认,不静默双跑(省额度/卡)。
  · **③ 防重复触达**:同一人 24h 内已触达就跳过(ledger `last_touched_date`)——重复 pitch 是风控 silent killer。

Step 4  LLM 打分              [§4]

Step 5  搜索通道(补量)       [operation-map §2B]  —— 仅当 A 档不足 target_qualified
  · ⚠ 先清默认预选(关键词/职位;城市默认空不污染),选择器已验证见 operation-map §2B → 清后 eval 读回 `.search-current-job` 文本 + get value 关键词框确认,再信结果。**职位下拉必须设成目标岗**(决定开聊/打招呼归属岗位)。搜完去 `searchFrame` 读结果。
  · 设 hard_filters;关键词矩阵+排序轮换;浏览详情免费;开聊耗畅聊卡→ Step 6 按 budget

Step 6  触达(按 touch_policy)  [§5]
  · 优先免费推荐通道打招呼;搜索来的按 budget.chat_cards 逐张记账,超停
  · 开聊前看"同事沟通进度",不重复 pitch
  · 每个外发动作:写账本 + 计当日额度 + 卡记账;动作间留间隔

Step 7  写账本 + 报告          [§6 §7]
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
5. 其余按数值:**A ≥ 7.5;B 5 ≤ score < 7.5;C < 5**。nice/company_bonus 加分;薪资/城市/到岗错配 → 每项 −1~2 分并在 one_line 点出。

**tier 取值:`A` / `B` / `C` / `unscored` / `A*`。** `A*` = **破格档**:技能明显 A 级、但被某条 cap 规则(如 <3年经验、略超带)压到 B,经**用户显式授权**破格触达的人。`A*` 不自动产生(不能靠数值升到 A*),只在用户拍板后由触达环节标注;计数上单列(不混入默认 `qualified_tiers:[A]`,除非策略显式把 A* 纳入)。ledger 用 `A*` 记这类候选人。

`one_line` 必含:最大亮点 + 最大顾虑(薪资/意愿/经验缺口等)。

---

## 5. 触达执行(touch_policy 档义)

| 档 | 自动做 | 报告给 |
|---|---|---|
| `report_first` | 零外发 | A/B/C 全名单+打分 |
| `greet_A_capped` | A 档自动打招呼(额度内,系统语) | B/C |
| `greet_custom` | A 档自动打招呼(自定义语,引用背景) | B/C |
| **`full`(默认)** | A 档自动 打招呼 **+ 回复后求简历** | B/C + A 触达结果 |

**⚠ full 档的"求简历"有平台前置门(2026-07-04 live 实测)**:候选人**未回复**时(会话 `[送达]`,非「沟通中」)求简历按钮是 `operate-btn disabled`,**点不动**。所以 full 档不是"打招呼当下顺手求简历",而是**打招呼 → 候选人回复 → 求简历**两拍。单次模式下,本轮打完招呼、候选人还没回,求简历就标 `pending-reply`,写进报告"待回执",下一轮(或阶段三心跳扫回执)再补。**别用 eval 强点 disabled 按钮**(无效且越红线)。

**永久红线(任何档、任何模式都不自动,只报告建议)**:换电话 / 换微信 / 约面 / 发布·关闭·删除职位 / 举报 / 批量标记不合适。`budget.chat_cards=0` 时不碰卡。
**限速冷却**:动作间留间隔;命中疑似风控(卡死/额度异常/提示)立即停、报告、不连续重启 Chrome。

---

## 6. 账本 ledger.jsonl(状态机 = 增量根基)

每候选人一行 JSON。**首轮若文件不存在先 Write 建空。** 状态机(覆盖账本实际用到的所有 status):
`found`(搜索命中未触达)`→ scored → greeted`(打招呼)`/ chatted`(畅聊卡开聊)`→`〔打招呼/开聊后候选人**未回复**时=`pending-reply` 状态,求简历还发不了,见 §5〕`→ replied`(对方回复、进「沟通中」,求简历解锁)`→ resume_received → contact_exchanged → interview → hired`。
旁路:`unfit`(命中 reject / C 淘汰)`/ no_reply / unscored`(数据不足待补)`/ inbound_msg`(对方主动来招呼、待处理)。

**去重键**:优先稳定 id;否则 `(name 或打码名前缀) + 最近公司 + 期望`多信号比对。**打码名(搜索)↔真名(推荐)可能是同一人**→ 命中相似即标 `possible_dup` 人工确认,不静默双跑(省额度/卡)。

字段:`id/name/masked/source/job/score/tier/status/first_seen/last_action/expect/company/actions[]/notes`。actions 记 `{t, act, cost(free|畅聊卡xN), result}`,可累加审计卡与额度。

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

playbook = 判定/调度/打分/触达策略/账本/报告(想什么、按序做);operation-map = 页面怎么点(URL/选择器/确认框/坑)。三条铁律(读用 eval、点用索引;聊天页走菜单;搜索页先清默认)在 operation-map §0,执行必守。

---

## 10. 已知限制(需 live 验证补选择器)

这些是执行层待补,遇到时优雅降级、别硬撞:
- ~~搜索页默认预选清除选择器~~ **✅ 2026-07-05 已验证补齐**(关键词/职位/城市三件套,见 operation-map §2B;城市默认空不污染)。
- ~~Step 0 健康指标无选择器~~ **✅ 2026-07-05 已验证**(每日打招呼额度=data-recruit iframe「沟通 X/200」、畅聊卡余量=搜索详情「剩余次数 xN」,见 operation-map §7d)。
- ~~full 档求简历异步闭环~~ **✅ 2026-07-05 已定义扫回执**(沟通中 tab ∩ ledger greeted/chatted → 求简历,见 Step 0.5 + operation-map §7c)。
- **约面(`.interview`)发起流程仍未实测**(用户暂缓;红线不自动,但操作本身待文档化)。
- **接口层(XHR)只抓了推荐侧**,搜索/消息端点待补;批量/长期自动化建议接 §7d 接口作主路径、DOM 抓取降为 fallback(抗改版)。
- **浏览器 id 非通用**:命令里用 `<YOUR_BROWSER_ID>` 占位,每次先 `browser-act browser list` 换成自己的。
- 招聘运营深度(分档定制招呼语、薪资破格建议、当日回复率反馈环、跨轮全局去重)——从"会点按钮"到"懂招聘"的下一步,见 REVIEW-20260704.md。
