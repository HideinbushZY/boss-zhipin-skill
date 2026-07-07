# Boss直聘 招聘者侧操作地图

> 目的:让 agent 照此丝滑操作 Boss 招聘者工作台,不必每次重新探索页面。
> 测绘方式:2026-07-03 用 browser-act(chrome-direct 接管真实 Chrome,账号=你自己的招聘者账号)逐板块实操验证。
> 执行工具:`browser-act --session <名> ...`;浏览器 id 全文用占位符 `<YOUR_BROWSER_ID>`。**换机/换人先跑 `browser-act browser list` 查你自己的 chrome-direct id,替换全文 `<YOUR_BROWSER_ID>`**(占位符不是可用 id,必须换成你自己的)。
> **本文所有 URL / 选择器 / 流程均为实测,非推演。** 页面改版后需重新验证。
> **提速实测(2026-07-04)**:同一任务「搜关键词→打开排名第一候选人简历详情」,盲探(最初)≈15 次浏览器调用(约 10 次是探索/走错路),照本文 **5 次、零探索、一次成功**——约 3× 更少调用,消除整个探索阶段。

---

## 0. 关键技术事实(agent 必读)

- **登录/接管**:chrome-direct 首次需 `browser open ... --allow-restart-chrome`(重启 Chrome 开调试端口,会丢未保存网页)。登录态在磁盘,重启不丢。
- **⚠️ 读用 eval,点/输入用 browser-act 索引(最重要的操作铁律)**:iframe 主内容**同源**(zhipin.com),`eval "document.querySelector('iframe').contentDocument..."` **只用来读** DOM(比截图快一个量级)。但**交互(点击/输入)必须走 browser-act `state` → 取 `[索引]` → `click <索引>` / `input <索引>`**(真实指针手势)。**eval 的 `element.click()` 往往打不开详情弹层/模态框**,别用 eval 做交互——这是本文档最容易被误用的一条(全新 agent 实测因此失败)。
- 本文出现的 CSS 选择器是**元素标识**(帮你在 state 里认出目标),不是让你 `querySelector` 后 eval-click;认出后仍用 browser-act 索引点击。
- **左侧菜单常驻**:菜单在 iframe 外,任何页面都可点。菜单项 class 固定(见下表),比 state 索引稳。
- **登录用户校验**:`eval "document.querySelector('.user-name')?.textContent"` → 应为"你的招聘者"。
- **访问废弃页会跳转**:如 `/web/boss/recommend` 显示"页面已停止维护 1s后跳转",等跳转即可。
- **命令确切写法**(全新 agent 别再查 `--help`;`<名>`=你的会话名):
  - 开会话 `browser-act --session <名> browser open <YOUR_BROWSER_ID> <url> [--headed --allow-restart-chrome]`
  - 读状态取索引 `browser-act --session <名> state`
  - 等待 `browser-act --session <名> wait stable --timeout 20000`
  - 输入 `browser-act --session <名> input <索引> "文本"` · 点击 `browser-act --session <名> click <索引>`
  - 截图 `browser-act --session <名> screenshot <路径>` · 读DOM `browser-act --session <名> eval "..."`
  - 抓包 `browser-act --session <名> network requests --filter zhipin.com --type xhr,fetch`
  - 关会话 `browser-act session close <名>`

---

## 1. 页面地图(招聘者工作台)

工作台首页 `https://www.zhipin.com/web/chat/index`(=沟通页)。左侧菜单 class → URL:

| 菜单 | 菜单 class | URL | 作用 |
|---|---|---|---|
| 职位管理 | `menu-position` | `/web/chat/job/list` | 发布/管理职位,看每个职位的看过我/沟通过/感兴趣 |
| 发布职位 | (职位管理内按钮) | `/web/chat/job/edit?encryptId=0&enterSource=2` | 多步发布向导 |
| 推荐牛人 | `menu-recommend` | `/web/chat/recommend` | **被动**:按职位算法匹配候选人,可直接「打招呼」 |
| 搜索 | `menu-geeksearch` | `/web/chat/search` | **主动**:全库搜人,开聊消耗「畅聊卡」 |
| 沟通 | `menu-chat` | `/web/chat/index` | 会话/CRM,漏斗标签(新招呼→沟通中→已约面→已获取简历…) |
| 意向沟通 | `menu-hunter-intention` | `/web/chat/intention` | **付费**:专属顾问辅助招人 |
| 互动 | `menu-interaction` | `/web/chat/interaction` | 对我感兴趣 / 我看过 / 同事推荐 |
| 牛人管理 | `menu-geek-manage` | `/web/chat/geek/manage_v2` | **表格式 ATS**,完整漏斗(单聊→…→已入职) |
| 道具 | `menu-prop` | `/web/chat/business/mall` | 道具商城(买畅聊卡等) |
| 工具箱 | `menu-toolbox` | `/web/chat/toolbox_v2` | 牛人管理/自定义打招呼语/已读筛选 |
| 面试 | 顶栏 | `/web/chat/report/interview` | 面试日历(约面结果汇总) |
| 账号权益 | 顶栏 | 右侧滑出面板(非新标签) | 权益/额度看板(见 §7d) |
| 招聘数据 | 顶栏 | `/web/chat/data-recruit` | 数据看板(见 §7d) |
| 自定义打招呼语 | 工具箱内 | `/web/chat/set/greeting` | 招呼语模板设置(见 §7d) |

---

## 2. 找人的两条核心通道(最重要)

Boss 招聘者找人有两条并行通道,**成本和机制完全不同**,agent 必须区分:

### 通道 A|推荐牛人(被动,优先用,成本低)
- 入口 `/web/chat/recommend`,标签:推荐 / 精选(带数字) / 最新。
- 右上角**按职位切换**(显示"职位名_城市+薪资带"),推荐结果是算法针对该职位的匹配。
- 卡片**显示候选人真名**(如"张伟 David(虚构示例)"),含年龄/经验/学历/求职状态/期望薪资/优势/工作经历时间线。
- 卡片直接有 **「打招呼」按钮**——走标准沟通额度,**不消耗畅聊卡**。
- 适合:agent 每天先扫推荐流,匹配度达标的批量打招呼(规则内)。

### 通道 B|搜索(主动,成本高,精准)

> **🗺️ 主动搜索操作逻辑·全盘(2026-07-07 实地重测,这一节是这个反人性页面的权威说明)**
>
> **① 架构**:搜索 UI(城市/岗位/关键词框/筛选/结果)**整个在 `iframe[name=searchFrame]` 里**——主文档 `querySelector` 够不到,browser-act `state` 也只在 frame 加载完后才索引到里面的控件。
> **② 🔴 冷加载直达 URL 不初始化**:`browser open /web/chat/search` 直达 → 页面**渲染出来了但控件读不到/点不了**(state 空、eval 拿不到、显示"正在加载")。**必须从左菜单点「搜索」(`dl.menu-geeksearch`)应用内路由进**,控件才活(同聊天页冷加载坑)。
> **③ 进页面就有三个"默认动作",全是坑**:
>   - **默认选中一个岗位**(账号的默认/最近发布的在线岗;`searchFrame` 内 `.search-current-job`)。🔴🔴**这个 jobId 实打实过滤/偏置你的关键词结果,不只是招呼归属**——实测:同一个关键词、同样筛选,**默认岗的前几名 与 `jobId=0`(不限)的前几名是完全不同的两组人**。→ **干净搜索前必须把岗位下拉改成「不限职位」(=jobId=0,纯关键词无偏置)或你真正的目标岗**,不设=被默认岗污染。
>   - **自动加载一批"热门词"结果**:空关键词下,页面已用默认岗的热门词自动搜了 ~15 人 + "根据热门词为您检索到以下牛人"提示。**这不是你搜的,别当结果读**。
>   - **城市默认空**(city input 空 = `city=-2` 不限/全国):**不污染**(round-3 曾高估城市污染,更正)。
> **④ 岗位下拉**(`.search-job-list-C .ui-dropmenu` → `.search-current-job`):选项=不限职位 + 账号各在线岗(下面还混搜索历史/热词);它决定 (a) 结果偏置 (b) 搜索结果里点打招呼/开聊的**招呼归属岗**——搜前必设。
> **⑤ 关键词框** `input[maxlength=20]`(默认空):输入触发 autoSuggest 下拉——**按原词搜就点搜索图标 `i.icon-search`,别点 suggest 项**;清空用 `keys cmd+a`+`Backspace`(React 受控,别 eval 设 value)。
> **⑥ 筛选**:学历(不限/本科及上/硕士及上/博士/自定义,单选默认不限)· 年龄(不限/20-25…/50以上/自定义)· **推荐筛选 chips**(985院校/多模态/算法/大模型/推理…=跟默认岗联动的 `extraStr.quickFilter` 建议,**默认不生效、点了才加**,干净搜别点)· 更多筛选(薪资/院校)。
> **⑦ 排序**:综合排序(默认,**动态洗牌**——同一搜索两次顺序会变,回找特定人别靠位置)/ 活跃优先 / 匹配度优先 + checkbox(过滤近14天查看 / 近30天未和同事交换简历)。
> **⑧ AI搜索**("开启AI搜索"按钮):另一种自然语言搜索模式,本次只只读未深入。
> **⑨ 干净搜索规范流程**:菜单进(非冷加载)→ 无视页面已有的热门词自动结果 → 岗位下拉设"不限职位"或目标岗 → 清空关键词框再输词 → 点 `icon-search`(别点 suggest)→ 城市/学历/年龄默认不限、按需设 → 去 `searchFrame` 读结果、详情走 `geek/info`(§7e)。
> **⑩ 强烈建议:上面这一整套 DOM 坑,接口层全绕过**——`geeks.json`(列表,直接传干净 `keywords`+`jobId`+筛选;要纯关键词传 `jobId=0`,要归属某岗传该岗 encJobId)+ `geek/info`(详情,破 canvas 反爬)。**DOM 只在"真开聊触达"时碰**(§7e)。

- 入口 `/web/chat/search`。**两个 iframe(2026-07-04 厘清)**:搜索前的默认视图在 `iframe[name=recommendFrame]`(所以直接读它=推荐池,round-3 误判"搜索无效"就是读错了 frame);**执行搜索后,结果渲染在 `iframe[name=searchFrame]`**——搜完必须去 searchFrame 读结果。
- **⚠️ 打开时有默认预选,必须先清再搜(否则结果被污染)**:搜索页初始会**默认选中一个沟通职位**(你账号的某个在线岗位)+ 可能带**城市** + 预填一个**热门词关键词**(如"智能客服"),并自动出一批"根据热门词为您检索到以下牛人"的结果。这些默认会 **scope/偏置** 你的搜索——**直接敲自己的词搜,结果仍可能被残留的默认职位/城市限定**,搜出不想要的人(尤其默认职位与你的目标不相关时)。做干净主动搜索前:① 清空关键词框默认值再输入;② 职位 dropdown 设目标职位或"不限"(见下条,决定招呼归属岗);③ 城市按需设(见下条,默认其实是空/全国,污染主要来自关键词+职位)。⚠️ 我自己早期的一次目标公司搜索就没清默认职位(默认岗恰好与目标方向相邻,遮住了这个坑),结果只是"看着对"。
- **✅ 清默认三件套·确切选择器(2026-07-05 实测补齐,§8 待补清零)**:
  - **关键词框** `input[maxlength=20]`:清除=`click <idx>` 聚焦 → `keys "cmd+a"` → `keys "Backspace"`(React 受控输入,别 eval 设 value,会被重渲染冲掉)→ `input <idx> "你的词"`。用 `get value <idx>` 复核。
  - **职位 dropdown** `.search-current-job`(在 `.search-job-list-C .ui-dropmenu` 里):`click` 它展开 `li` 列表(不限职位 / 你的各在线职位)→ `click` 目标职位的 `li`。复核=eval 读 `.search-current-job` 文本。**⚠【关键·别当事后细节】这个下拉不只是过滤——它决定"你在搜索结果里点打招呼/开聊时,招呼归属哪个岗位",搜前必须设成目标岗,详见下方专条。**
  - **城市** input 在 `.search-city-kw` 内:**默认是空(=全国/不限),所以城市一般不污染**——这是 round-3 高估"城市污染"的更正。要设城市:`click` 该 input → 弹 `ul.dropdown-province`(级联:热门/北京/上海/广东…/不限,`li.first-menu`)→ 点省再点市(深圳=点广东→深圳),或点"不限"清。
  - **复核铁律**:清+设完,`eval` 读回 `.search-current-job` 文本 + `get value` 关键词框,确认无残留默认再点搜、再信结果。
- 关键词框 `input[maxlength=20]` + `i.icon-search` 执行(输入会弹 suggest 下拉,按原词搜就点 icon,别选下拉)。清空关键词框用 browser-act `keys "cmd+a"` + `keys "Backspace"`(React 受控输入,别 eval 设 value);城市框是另一个 `input`(在 `.search-city-kw` 内)。
- **⚠️ 职位下拉决定"打招呼归属的岗位"(2026-07-04 实测)**:搜索页的职位 dropdown(`.search-current-job`)默认可能是账号别的岗位。**你在搜索结果里点打招呼,招呼是发给"当前选中职位"的**——所以搜 ASR 人之前**必须把职位下拉改成"语音识别(ASR)算法工程师"**,否则会把人约到错的岗位。下拉项:不限职位 / 你的各在线职位。
- **✅ 全局牛人搜索确实可用(2026-07-04 更正 round-3 的误判)**:输入公司名(你的目标公司)或关键词→点 icon-search→**去 `searchFrame` 读结果**,能搜到全库牛人(masked 打码名+"热搜"标)。round-3 搜"会议转写"以为无效,真因是①关键词太窄命中少、②读错 frame(读了 recommendFrame)。**公司名命中很足**;结果卡是 `a[parent_class=geek-info-card]`,点开=候选人详情(含工作经历、期望城市)。
- **⚠️🔴 搜索畅聊卡「开聊」= 捆绑动作,自动索要微信/电话(2026-07-04 实测,红线警告)**:搜索结果详情里的大按钮 `button.btn-sure-v2`「搜索畅聊卡(N/17)」**不是普通打招呼**——点它=**消耗 3 张搜索畅聊卡** + **系统一键"发起沟通并索要简历/微信/电话"**(开聊成功提示原文:"已为您发起沟通并索要简历/微信/电话,该牛人已开通虚拟电话可直接联系")。**即畅聊卡开聊内置了 换微信/换电话 的 PII 请求**,落在永久红线里。**用畅聊卡前必须先向用户确认接受这个捆绑**;按钮紧挨 举报/不合适,认准 `btn-sure-v2` 再点。**💰成本:每次开聊消耗 3 张搜索畅聊卡(不是1张)——按钮标"搜索畅聊卡(3/N)"里的 3=单次消耗、N=剩余(实测 17→14)。做卡预算换算时按 3/开聊 算(4 卡预算=只够 1 次开聊)。**账号搜索畅聊卡余量在详情右侧"畅聊卡 剩余次数 xN"。
- 筛选:学历 `span.degree-item`、年龄 `span.age-item`(单选,active class 标当前);更多筛选含薪资/院校等。
- 排序:综合排序(默认)/ 活跃优先 / 匹配度优先。**综合排序动态洗牌**,回找特定人要靠"关键词+年龄+学历"组合逼近。
- 结果卡容器 `li.geek-info-card`(内含 `<a parent_class=geek-info-card>`),姓名打码(如 张**);列表**虚拟滚动**(一次渲染 2-4 张,逐屏滚)。
- **🔴 读候选人=接口优先,别靠 DOM 点卡片(2026-07-07 更正)**:searchFrame 里结果卡的 `<a>` browser-act **state 时有时无地索引不到**;卡片是 `ka=search_click_open_resume` 用 JS 在**新标签页**打开、简历**画在 canvas 上反爬**(gray 灰度 `encryptGeekDetailGray`),**DOM 读不到、跟不到新标签、截不到干净详情**。→ **列表用 `geeks.json`、详情用 `geek/info` 接口(§7e),端到端接口,不碰这套脆弱 DOM。** DOM 卡片点击只在"真要开聊触达"时才用(且开聊详情页在灰度账号上也可能是 canvas,行为按账号异)。
- 开聊消耗**畅聊卡**(见 §5 成本);触达仍走 UI。

> 一句话:**能推荐就别搜索**(省畅聊卡);**搜索的"找+读"全走接口层(§7e:geeks.json 列表 + geek/info 详情),DOM 只在开聊触达时碰**;搜索用于推荐覆盖不到的精准定向。

---

## 3. 候选人漏斗 / 状态机(异步循环的骨架)

同一套漏斗有两个视图:

**沟通页 `/web/chat/index`(会话视图)** 顶部标签:
`全部 / 新招呼 / 沟通中 / 已约面 / 已获取简历 / 已交换电话 / 更多{已交换微信 / 收藏 / 不合适 / 牛人发起 / 我发起 / 道具来源 / 群聊}`
- 左栏:职位过滤下拉 + 全部/未读 + 批量;会话项=头像+姓名+应聘职位+末条消息+时间;**只展示近30天联系人**。
- 会话内操作栏(上次畅聊实测):表情 / 常用语 / 简历 / 手机 / 消息 / 时钟 / 电话 / **发送**。

**牛人管理 `/web/chat/geek/manage_v2`(表格视图,更完整)** 漏斗标签:
`单聊 → 沟通中 → 已约面 → 已发offer → 已入职 / 不合适`
- 筛选:应聘岗位 / 学历 / 工作经验 / 年龄 / 求职状态 / 新招呼 / 我发起。
- 表格列:牛人(勾选框+名) / 基本信息(学历·年龄·经验·薪资) / 最近工作经历;支持**批量勾选**、分页。

> **状态机设计直接用这套漏斗**:`新招呼/单聊 → 沟通中 → 已约面 → 已发offer → 已入职`,失败态 `不合适`。牛人管理的漏斗比沟通页更全(含 offer/入职),做进度跟踪以它为准。

---

## 4. 各板块操作细节

### 4.1 职位管理 `/web/chat/job/list`
- 顶部:「发布职位」按钮(state 索引变动,认文案)、搜索框 `input#search`、右上「批量获得投递,不达保退」(付费引流)。
- 状态标签:全部职位 / 开放中 / 待开放 / 审核不通过 / 已关闭。
- 职位卡 `li.job-jobInfo-warp`:标题 + 城市/经验/学历/薪资/类型 + 三数据块(看过我 `看过我` / 沟通过 / 感兴趣)+ 状态 + 到期日。
- 卡片操作:**编辑 / 关闭**(直接可见的主按钮,职位卡右侧)/ 预览 / 分享 / 复制 / **删除** / 上传到职位库(后几个在「更多」`...` 悬浮菜单里)。
- **✅ 关闭职位流程(可操作,2026-07-07 补)**:关闭是**可逆**动作——关掉的岗进「已关闭」页签,点「重新开放」即可复活,**候选人对话/简历/漏斗数据全保留**;故不列永久红线(删除才是不可逆红线)。操作:
  - **① 核对岗位(硬门,防误关)**:职位卡按 state 索引点「关闭」前,先读**该卡标题**确认=目标岗(列表里多个在招岗各有「关闭」,误点会关错岗——同"发消息核收件人"铁律)。取法:每张卡的「关闭」在 `.job-jobInfo-warp` 内、和标题同卡;先 eval 读目标卡标题匹配,再取该卡「关闭」的 state 索引点(实测索引=该卡操作区 `[编辑][关闭]` 相邻)。
  - **② 关前向用户确认**:报"要关闭『<岗位名>』(N沟通过/M简历),这些沟通/简历随岗归入已关闭,可重新开放"→ 用户点头。
  - **③ 点「关闭」→ 确认框「确定关闭职位吗?关闭职位后将不再产生招聘效果」(暂不关闭/关闭职位)→ 点「关闭职位」→ 验证**该岗进「已关闭」页签。
  - `.job-jobInfo-warp` 在 iframe 里,读卡用同源 eval;**确认框弹在主 document(非 iframe)**。

### 4.2 发布职位 `/web/chat/job/edit`(多步向导,**2026-07-07 真机发布过审实测**)
入口:职位管理页点 `[bzl-button.publish-btn]`(shadow DOM)进向导(别冷加载 edit URL)。单页表单,填完点底部 `button[type=submit]`「发布」。
- **🔒 硬约束**:发布后「招聘类型/职位名称/职位类型/工作城市」**永久不可修改**(向导顶部有此提示);经验/薪资/学历/JD 等发布后可改。**提交前必回读这 4 项给用户确认**(安全门,见 §6)。
- **字段与填法(索引随每步操作漂,每步重取)**:
  - 招聘类型:`chose-item` 单选,社招全职默认(核 active);是否驻外:`chose-item`,选「境内岗位」。
  - 职位名称:`input[name=jobName]`,`input <idx>` 直接写。
  - 职位描述:`textarea`,`input <idx>` 写 JD(**禁 QQ/微信/电话/特殊符号**否则校验挂;用「岗位职责/任职要求」纯文本标题即可,别用生僻符号)。
  - 职位类型(锁死):`input[name=jobCategory]` → 点开弹「请选择职位类型」推荐标签(按你职位方向 Boss 推荐几个,如 硬件产品经理/AI产品经理 等),每个是 `div.job-recommend-content_item`(**注意:前面的「产品经理」是分组标题不是选项,别点错**);选叶子后弹层自动关、input 回填。要更细类目点「查看全部职位类型」。
  - 经验/学历:`ui-select-selection` 下拉,`click <idx>` 开,选项是 `ui-select-item`(经验档:不限/1年以内/1-3/3-5/5-10/10年以上——**无自定义区间**)。
  - 薪资:三个 `ui-select`(最低月薪/最高月薪/薪资月数)。**⚠坑:薪资下拉选项渲染在 portal,browser-act `state` 索引不到,只能 eval 读 `.ui-select-dropdown` + eval-click 目标项**(如 `30k`/`60k`/`16个月`;选最低后最高自动填个默认要改;月数只单值 12-24 个月,**无区间**)。选项文本小写 `k`。
  - 工作地址(锁死城市来源):`input[placeholder=选择工作地点]` → 弹「请选择工作地址」列账号已存地址(`div.address-item`,radio `normal-radio`)→ 选目标城市那行 → 点 `btn-sure-v2`「使用该地址」→ input 回填,**城市由此定死**。
  - 职位关键词:可能自动带一个;`add-skill` 加。
  - 协议「已阅读并遵守《招聘行为管理规范》」无独立勾选框,点「发布」即视为同意。
- **发布 → 弹「审核通过·当前职位已通过审核」**(一般秒过审)+ 盖一个**付费曝光升级推销弹层**(限时升级/预计增加回复投递)——**只点 `boss-popup__close` 关掉,绝不买**(付费=红线)。关掉后进职位管理「开放中」即验证成功。
- 发布失败(页面不跳转)→ 查校验:JD 含违禁符号 / 必填项空。别反复点。

### 4.3 推荐牛人 — 见 §2 通道 A。

### 4.4 搜索 — 见 §2 通道 B。畅聊流程(实测):
详情弹层 → `span.icon-change-job` 开职位选择 popover → 选 `li`(active 标当前)→ 点「搜索畅聊卡(N/M)」→ 成功弹窗「使用成功-已为您发起沟通并索要简历/微信/电话」,按钮变「继续沟通」。系统自动发:职位卡+默认开场白+索要简历/联系方式。

### 4.5 意向沟通 `/web/chat/intention`(**付费**)
- 顾问辅助招人:发现(付费专享)/ 待下单 / 我的订单;子标签 付费专享 / 收藏牛人 / 沟通中牛人。非免费主线,agent 默认不碰。

### 4.6 互动 `/web/chat/interaction`(iframe `interactionFrame`)
- 标签:对我感兴趣 / 我看过 / 同事推荐。卡片 `div.card-inner.new-geek-wrap`。
- 注意:搜索详情弹层的浏览**不一定计入"我看过"**(有延迟或不计),别用它回找。

### 4.7 牛人管理 — 见 §3。

### 4.8 面试 `/web/chat/report/interview`
- 月历(列表/宫格切换),绿标=已约面;当前暂无面试。**约面动作在会话内发起**,结果汇总到此日历。

### 4.9 道具 `/web/chat/business/mall`
- 道具商城,买畅聊卡等付费道具。

---

## 5. 成本 / 额度模型(agent 决策前必查)

- **畅聊卡(搜索畅聊卡)**:主动搜索开聊消耗。按钮文案 `搜索畅聊卡(N/M)` = **单次消耗 N / 剩余 M**。**⚠ 实测单次开聊消耗 3 张(2026-07-04,17→14),以 §2B 的详细说明为准**(此前"消耗 2"的旧记为误)。详情弹层右侧"畅聊卡 剩余次数 xN"也可见。做卡预算换算按 3/开聊 算。
- **打招呼(推荐牛人)**:走标准沟通额度,**不耗畅聊卡**——优先用。
- **意向沟通 / 批量获得投递**:付费服务。
- **账号权益**页(顶栏,新标签):看各类额度/权益总览。
- 决策规则:**能推荐打招呼就别搜索畅聊**;消耗畅聊卡/付费道具前必须报数+等用户确认。

---

## 6. 安全门(写进 skill 时做成硬规则)

- **消耗权益**(畅聊卡、道具、付费服务)→ 先报数量,等用户明确同意。
- **外发内容**(打招呼、发消息、求简历)→ 发出前确认(策略寻访模式按 touch_policy 档授权);这些代表公司雇主品牌,不可撤回。会话内发消息必过三验(§7c)。
- **关闭职位**(可操作,发出前确认 + 核对岗位)→ 可逆动作(可重新开放,数据保留),agent 可代关,硬门=先核对是哪个岗+关前确认+关后验证(见 §4.1)。
- **发布职位**(可操作,提交前须回读 4 个锁死字段+内容给用户确认 + 不买曝光)→ 对外公开动作、锁死字段不可逆,agent 可代填向导+提交,但内容由用户拍板(见 §4.2)。
- **永久红线(与 SKILL.md 安全门同口径,任何模式都不自动,只报建议、人来点)**:换电话 / 换微信 / 约面 / **删除职位** / 举报 / 批量标记不合适 等最深的 PII/承诺/**不可逆**破坏性动作(关闭/发布已移出=可逆/可用户确认后代做;删除仍是唯一红线)。
- **发职位描述**禁填 QQ/微信/电话(平台会封号)。
- **限速**:低频、人在环;高频批量触达会触发招聘方账号风控(账号是公司资产)。命中风控立即停,不换通道重试。
- 每次会话结束 `session close` 释放用户 Chrome。

---

## 7. 已踩坑速查

| 现象 | 处理 |
|---|---|
| 综合排序洗牌,找不到特定候选人 | 用「关键词+年龄段+学历」筛选逼近,逐屏 grep 姓名 |
| 结果列表只渲染几张卡 | 虚拟滚动,`scroll down` 逐屏 |
| 详情弹层内容读不到 | 等待+重新 state,或直接 screenshot |
| 弹层内滚动截图 | `screenshot --full` 无效,`scroll down` 步长 ≤650 分页 |
| 详情弹层切候选人 | `div.turn-btn.next/.prev` 直接切,不用关弹层 |
| 点菜单超时报错 | 多为渲染慢,`sleep 3` 后 `eval "location.href"` 确认已到位 |
| 访问 `/web/boss/recommend` 空白 | 废弃页,会自动跳 `/web/chat/index` |
| 🔴 消息发给了错误的人 | 会话列表是**筛选页签作用域**的(切「新招呼/沟通中」后原目标可能不在列表)→ eval 找人失败若静默返回,当前会话还停在上一个人。**发送前必读 `.name-container .name-box` 核收件人**(见 §7c 收件人核验) |

---

## 7b. 发布职位流程(2026-07-03 实操,含踩坑)

**表单结构**(`/web/chat/job/edit`,内容在同源 iframe,可 contentDocument 直读):
- 职位名称 `input[name=jobName]`;职位描述 `textarea`(用 value setter + input 事件写多行);职位类型 `input[name=jobCategory]`(点开弹「请选择职类」模态,搜索框搜"语音"→选 `li` **语音算法**,ASR 岗准确类目;无"语音识别"叶子)。
- 招聘类型默认「社招全职」、驻外默认「境内岗位」——通常无需改。
- 第2步:经验/学历/薪资均为 `.ui-select-selection` 自定义下拉,**必须用 browser-act state 索引点 `li.ui-select-item`**(eval 点 option 不稳)。
- 薪资三联下拉:最低/最高/月数(30-50K·14薪);**最低选完会联动改最高的默认值**,务必按 最低→最高→月数 顺序逐个校验(读 `.ui-select-selected-value`)。
- 工作地址:账号预填(账号会预填你公司的工作地址→城市);简历接收邮箱 (你账号配置的简历接收邮箱)。
- 底部「发布」按钮提交(发布后 招聘类型/职位名称/职位类型/工作城市 锁死)。

**发布成功后**:弹出付费「曝光刷新卡」(¥328,扫码支付)——**可选付费,直接关 `.boss-popup__close` 不付**;职位列表页顶部也会有"去升级"倒计时同类推销。新职位状态「开放中」,平台审核后对候选人可见。✅ 全流程 2026-07-03 已完整跑通一次。

**几个易变索引经验**:类目/经验/学历/薪资下拉的 state 索引每次操作后会变,每步都要重新 grep;`.ui-select-item` 选项可能在下拉内需 `scrollIntoView` 才进 state;月数下拉的 `.ui-select-dropdown` 有时 state 抓不到,可用 `eval` 过滤 `offsetParent!==null` 的可见 dropdown 直接 `.click()`;工作地址弹「请选择工作地址」列出你账号已存的工作地址(可能多个),点目标城市对应的「使用该地址」,城市由此决定。

**⚠️ 重大坑(2026-07-03 实测):** 在薪资下拉反复用 eval 点选时,某次误触打开了 **C 端首页(zhipin.com/)新标签**,导致 browser-act 焦点切到新页 + **招聘者登录态掉线**(跳 `/web/user/?ka=bticket` 扫码登录,user=NONE),**已填表单草稿全部丢失,无自动草稿**。教训:
1. 下拉优先用 **state 索引点 `li.ui-select-item`**,不要用 eval 遍历点 option(易误触旁边链接/跳页)。
2. 每步操作后 `eval "location.href"` 确认没跳出 `/web/chat/job/edit`。
3. 发布表单**无草稿保护**,掉线=重填;填表期间不要触发任何可能开新标签的点击。
4. 掉线后 re-login 需用户手机(扫码/验证码),agent 无法代做 → 属人工接管场景。

## 7c. 沟通/打招呼流程(2026-07-03 部分实测)

- **推荐牛人「打招呼」已验证**:点卡片 `button` 打招呼 → 弹「已向牛人发送招呼」,发的是**系统默认开场白**("你好,我司急聘XX一职,请问考虑么?"),非自定义。想个性化需进会话补发。卡片按钮随后变「继续沟通」。走标准额度,未见扣畅聊卡。
- **会话内元素**(`/web/chat/index` 选中某会话):消息输入 `#boss-chat-editor-input`(contenteditable div,非 textarea)、发送 `.submit`、工具栏 `求简历`=`.operate-btn`、`约面试`=`.interview`、还有 换电话/换微信/不合适;候选人简历入口「在线简历」「附件简历」在会话头部;快捷回复气泡"你好啊可以聊一聊~"/"不好意思不太合适哦"。
- **⚠️ 环境稳定性坑(2026-07-03)**:一次会话里连续 发职位→推荐打招呼→大量导航 后,`/web/chat/index`(沟通页 SPA)**反复卡在"加载中,请稍候"无法初始化**,同时 browser-act 的 chrome-direct **CDP 会话反复掉线**(一小段内掉 3 次,重开需 `--allow-restart-chrome`)。职位管理页能导航但聊天页起不来。当时**误判为软风控**。**后经验证:并非风控封号**(登录态一直有效,职位管理页正常),真实原因是**沟通页冷加载 URL 起不来**(见下条「关键破解」)+ CDP/MCP 断连churn。**保留的教训仍成立:操作要低频、分批、间隔;不要连续重启 Chrome(每次重启还可能触发登出)。**
- 结果:①打招呼(候选人B(示例),对方[已读])②会话回复(候选人A(示例))③求简历(候选人A(示例))**三个已全部跑通** ✅。
- **关键破解**:沟通页**冷加载 URL(navigate 直达 `/web/chat/index`)会卡死在"加载中"**,但**从左侧菜单点「沟通」进入(应用内路由)则正常渲染**——重启 Chrome 后务必走菜单进入,别用直达 URL。
- **⚠️ 桥掉线恢复姿势(2026-07-04 实测)**:关闭 session 后 chrome-direct 可能重连不上,`browser open` 一律报 `230404 Unknown error`,连 `--allow-restart-chrome` 也报错——这是 **browser-act 控制面**问题(此时 `stealth-extract` 仍正常=cloud API 没挂;`curl localhost:9222/json/version` 返回空/404=旧调试口是僵尸)。**别急着 kill 用户 Chrome**(登出需手机扫码,不可逆)。恢复步骤:①`osascript -e 'tell app "Google Chrome" to count windows'` 确认 Chrome 已就绪且能被 AppleScript 控制(mid-restore 时会 -1712 超时,等它稳定);②Chrome 稳定后用 **`browser open <id> <url> --headed --allow-restart-chrome`** 重试即可恢复。核心:失败多因 Chrome 忙于恢复标签页,等就绪再带 `--headed --allow-restart-chrome`。
- **🔴 0 窗口时别 restart,会登出(2026-07-05 实测,踩过)**:若 `count windows` 返回 **0**(用户把 Chrome 窗口都关了,进程还在)或报 `CDP permission retry window expired`,**此时 `open -a` 新开窗 + `--allow-restart-chrome` 有很大概率把 Boss 登录态冲掉**——登出后是微信扫码/短信验证码页(`/web/user/?ka=bticket`),agent 代替不了,必须用户手机重登。**对策**:0 窗口时**先只 `open -a "Google Chrome"` 把已有窗口/会话唤起、等 5-8 秒,先不加 `--allow-restart-chrome` 试 attach**;能连上就别 restart。实在要 restart 前,先确认这是"桥僵尸"而非"窗口全关",宁可停下让用户手动把 Boss 标签页点出来,也别赌 restart。登出=不可逆(需用户扫码),代价远高于多等一会。
- **⚠️ 推荐流深滚后 state 索引退化(2026-07-04 实测)**:推荐列表虚拟滚动多屏后,`browser-act state` 只索引到 ~56 个元素、多数卡片「打招呼」按钮拿不到 `[index]` → 无法索引点击(且铁律禁止 eval 强点)。对策:**要触达的候选先滚到列表靠前再取 index**;或**分批——每滚一屏就把该屏的 A 触达完再滚**,别一次滚到底再回头找按钮(列表还会因打招呼/相似注入而 re-flow)。
- **求简历流程**:点会话工具栏「求简历」→ 弹确认框「确定向牛人索取简历吗?」→ 点「确定」→ 对话流出现「简历请求已发送」,按钮置灰。
- **⚠️ 求简历有前置门(2026-07-04 live 实测)**:刚打招呼、候选人**未回复**时(会话状态 `[送达]`,非「沟通中」),求简历按钮是 **`operate-btn disabled` 灰态,平台禁用点不动**。**必须候选人先回复(进入「沟通中」)求简历才可用**。所以"打招呼当下顺手求简历"做不到——它是候选人回执后的动作。**别用 eval 强点 disabled 按钮**(无效且越红线)。选择器补正:工具栏里 `.operate-btn` 有多个(求简历 在 `.operate-exchange-left` 内、`不合适` 也是 `span.operate-btn`),**认元素靠文本"求简历"更稳**,别只凭 `.operate-btn`。
- **✅ 扫回执机制(2026-07-05 实测,支撑 full 档异步闭环)**:判断"某个已打招呼的人回没回"有两条互补信号:
  - **权威口径=「沟通中」漏斗过滤 tab**(`div[title=沟通中]`,进沟通页后点它):列出**所有已进入活跃对话的候选人**。一个你打过招呼的人**出现在沟通中 = 他回复了 = 求简历解锁**。这是扫回执的主判据。⚠ 实测(2026-07-05):**沟通中 tab 是账号全局、含 inbound(对方主动来的、还含别的岗位的人)**——所以别直接把整个 tab 当"我的回执名单";**做法是拿 tab 名单去 ∩ ledger 里 `status∈{greeted,chatted}` 的人**,交集才是"我主动触达且已回复"的有效回执(inbound 的 status 是 `inbound_msg/resume_received`,天然被交集排除)。
  - **辅助口径=会话列表每行的 `.status` 文本**:`[送达]`=你的消息已送达未读、`[已读]`=对方读了但没回——**这两种都说明"最后一条是你发的"=未回复**;若某行**没有 `.status`**(最后一条是对方的气泡),且他是你主动触达的人 → 他回复了。(注意:inbound 候选人天然"没 status"因为是他先发的,别误判成"回复"——扫回执只对 `status=greeted/chatted` 的账本条目做。)
  - **扫回执动作**:进沟通页 → 点「沟通中」tab → 取候选人名单 → 与 ledger 里 `status∈{greeted,chatted}` 的人取交集 → 对交集里每人:打开会话 → **核收件人**(`.name-container .name-box` = 该人名,§7c 三验①,不等则停)→ 点工具栏「求简历」(此时应 enabled)→ 确认框「确定向牛人索取简历吗?」→ 确定 → ledger 记 `request_resume`。
- **会话回复流程**:输入框 `#boss-chat-editor-input`(contenteditable,browser-act input 可写)→ 点 `.submit`「发送」→ 消息气泡显示「送达」,输入框清空。
- **🔴 发消息前必核收件人(2026-07-06 误发事故,真实踩过)**:一条本应发给 A 候选人的消息发给了 B。三个 bug 叠加:①**会话列表是筛选页签作用域的**——切到「新招呼」后,「沟通中」里的目标人不在可见列表,eval 找人静默失败;②eval 打开会话的代码**找不到人也返回成功**(`if(it){click()} return 'ok'` 这种无条件返回),当前会话仍停在上一个人;③发送前只验了**内容**=批准稿,没验**收件人**。防呆三验(缺一不发):
  - **① 收件人**:发送前 `eval "document.querySelector('.name-container .name-box')?.innerText.trim()"` **必须等于目标姓名**(这是聊天区头部的对方名,不是左侧列表的 `.geek-name`);不等=当前会话不是目标,停手重开。
  - **② 内容**:`#boss-chat-editor-input` 的 innerText 与批准稿逐字一致。
  - **③ 送达回读**:发后重读 ①(线程还是目标人)+ 最后一条气泡=刚发内容且带「送达」。
  - 打开会话的 eval **必须条件返回**(`if(!it) return 'NOT-FOUND'`),调用方**必须检查返回值**、不许 `>/dev/null` 丢弃;找不到就先切对筛选页签(目标在哪个漏斗就切哪个)再找。
- **实战侧记**:ASR 岗发布后 1-3 小时内自然涌入十几个候选人(含主动发简历/微信的),说明深圳 ASR 岗位供给充足;沟通列表按最新消息时间排序、虚拟滚动,回找特定人可能需 eval 定位或搜索。

## 7d. 只读页/配置/接口层(2026-07-03 批量验证)

- **账号权益**(顶栏,右侧滑出面板,非新标签):企业版,职位发布权益 **5 个在线职位**;**每日使用权益:主动查看=不限 / 沟通总量=200 个 / 回复=不限**。→ 打招呼/沟通日限=**200/天**,查看和回复不限。
- **招聘数据**(`/web/chat/data-recruit`):日报/周报/月报/VIP权益数据;今日概览 8 指标(我看过/看过我/我打招呼/牛人新招呼/我沟通/收获简历/交换电话微信/接受面试,均带昨日对比)+ 趋势图(近7天/近30天/自定义)。招聘漏斗看板。
- **✅ 健康检查读法(2026-07-05 实测,支撑 playbook Step 0 自动判断)**:数据在**该页的 iframe 里**(顶层 body 几乎空)。读法:`eval` 遍历 `document.querySelectorAll('iframe')`,取 `contentDocument.body.innerText` 里含 `/200` 的那个 frame,解析:
  - **每日打招呼额度**:文本里的「沟通 **X/200**」(实测当时 5/200、"当前剩余195个打招呼权益")——这是每日主动沟通日限的权威计数。**阈值:剩余 < ~10 就收着点/停,别撞 200 上限触发软风控。**
  - **今日漏斗**:我打招呼 / 我沟通 / 收获简历 / 交换电话微信 / 接受面试 的当日数(可核对外发是否真的发出去了、有没有异常掉零)。
  - 页面里还有**道具商城入口**(搜索畅聊卡/置顶卡/精准置顶卡「购买」,直豆可抵扣)——即"没卡了去哪买"的入口,但购买涉及付费,agent 只报告不自动买。
- **健康检查完整清单(Step 0 建议按序)**:① 登录 `eval "document.querySelector('.user-name')?.textContent"` = 招聘者名;② 每日打招呼额度(上面的 X/200,剩余够不够本轮预算);③ 搜索畅聊卡余量(搜索结果详情右侧「畅聊卡 剩余次数 xN」,或按钮「搜索畅聊卡(3/N)」的 N);④ 风控体感(聊天页是否反复卡"加载中"、额度是否异常、动作是否被拒)——命中就停手冷却。前三项有选择器可自动读,第④项靠行为观察。
- **工具箱**(`/web/chat/toolbox_v2`,iframe):牛人管理 / **自定义打招呼语** / 已读筛选。
- **自定义打招呼语**(`/web/chat/set/greeting`,账号设置内,iframe):开关(默认开);**通用** + **按职位设置招呼语**两级;风格预设 常规/幽默/礼貌/诚恳/**自定义**;占位符 {职位}{姓名}{公司};默认模板"你好,我司急聘{职位}一职,请问考虑么?"。→ 这就是推荐/搜索打招呼发的开场白来源;**措辞属品牌语音,改动应由用户定**。
  - **选择器(2026-07-06 只读补录,零点击零保存)**:控件全在 iframe 里(`document.querySelector('iframe').contentDocument`)。总开关 `div.switch > span.ui-switch`(开=带 `.ui-switch-checked`);两级 tab `.greeting-tab .tab-header .tab-item`(选中=`.tab-item.select`);当前生效语显示在「未按职位单独设置时,将使用:」之后;风格预设 `.list-tab > p`(选中=`p.active`);各风格的现成模板列表在 `.tab-common .list-container`(占位符以「(示例姓名/公司/职位)」内联展示)。
  - **⚠「自定义」的输入框和保存按钮要选中「自定义」后才渲染**,本次守零改动承诺未点(账号级持久配置,改了影响之后所有系统打招呼文案)。真要设置的完整路径:用户定措辞 → state 取「自定义」`p` 的索引 click → input 写内容 → 找保存按钮 click(届时把这两个选择器补进来)。agent 对此页默认**只读不写**;管线的定制招呼语不走这里,走"打招呼→会话内补发定制句"(playbook §11.1,§7c 会话流程)。
- **换电话确认框**:「确定与对方交换手机吗?」(取消/确定);**换微信确认框**:「确定与对方交换微信吗?」(取消/确定)——与求简历同款二次确认。均属外发 PII 请求,发前须确认。
## 7e. ✅ 接口层(2026-07-06 真机抓包实测,推荐通道可作主路径)

**怎么调**:同源 sync XHR,借页面已有 cookie,eval 里跑(异步 fetch eval 可能返回前没 resolve,用同步 XHR 最稳):
```js
(() => { const x=new XMLHttpRequest(); x.open('GET', URL, false); x.send(); return JSON.parse(x.responseText); })()
```

### 🟢 推荐候选人列表(主路径,解决虚拟滚动索引退化)
`GET /wapi/zpjob/rec/geek/list?jobId={encJobId}&page=N&age=16,-1&degree=0&experience=0&salary=0&keyword1=-1&gender=0&major=0&intention=0&activation=0&cardType=0`
- **响应**:`zpData.geekList[]`(**每页 15 人**)+ `zpData.hasMore`(还有没有下一页)→ **翻页拉 `page=1,2,3…` 直到 hasMore=false,拿全量、无虚拟滚动、无 state 索引退化**。
- **每个候选人字段**(关键):
  - **`haveChatted`**(0/1)、**`isFriend`**(0/1)= **Boss 自带的"已聊过/已是好友"去重标**(见 §7f 去重);
  - `searchChatCardCostCount` = 触达要几张畅聊卡(推荐通道通常 0=免费打招呼);
  - `hasAttachmentResume`、`recommendReason`;
  - `geekCard{ geekName, geekGender, geekWorkYear(经验年), geekDegree, freshGraduate(应届), geekDesc(优势自述), lowSalary/highSalary/salary(期望薪资), expectPositionName(期望职位), expectLocationName(期望城市), ageDesc, geekEdus(教育), geekWorks(工作经历), encGeekId, securityId(动作 token,打招呼/开聊要用) }` —— **就是 DOM 卡片上的全部信息,但是干净 JSON**。
- **encJobId 怎么拿**:滚动推荐列表时抓包这个请求的 `jobId=` 即得;或选中职位后从 recommend iframe 的 `?jobid=` / `rec/f1/card?jobId=` 请求里取。是加密串(如 `0a1b2c3d4e5f6g78hIJK-9LmN(虚构示例,格式相仿)`),账号/职位相关,别硬编码。
- **筛选参数**:age/degree/experience/salary 等直接对应 hard_filters(格式如 `age=16,-1` 区间、`degree/experience/salary=0` 表不限),接口筛比页面点更精确。

### 🟢 搜索通道(主路径,2026-07-06 实测)—— 接口反而比 DOM 干净,直接跳过"清默认"这套 UI 操作
真正的关键词搜索端点是 **`geeks.json`**(不是 `searchRecommend.json`——那个是打开搜索页时的"默认推荐搜索",带热门词污染):
`GET /wapi/zpitem/web/boss/search/geeks.json?page=N&jobId={encJobId}&keywords={关键词}&city={cityCode}&experience={min,max}&salary={min,max}&age={min,max}&degree={code}&schoolLevel=-1&gender=-1&applyStatus=-1&source=1&filterParams={JSON}`
- **`keywords`** = 你的搜索词(URL 编码);多个词可用它自带的分词(响应 `zpData.segs` 会回显解析结果如 `语音识别`语音算法`asr`)。
- **`jobId`** = encJobId(触达归属岗,同推荐通道那个)。
- **筛选参数**:`city`=Boss cityCode(`-2`=不限;具体码从 `GET /wapi/zpCommon/data/getCityList` 拿)、`experience/salary/age`=`min,max` 区间(`-1,-1`=不限)、`degree`=学历码(`0`/`-1`=不限、`201`≈本科)。`filterParams` 是个 JSON(sortType/region 等),可给最小 `{"sortType":1,"region":{"cityCode":"-2"}}`。
- **✅ 关键好处:接口直接构造干净 `keywords`+筛选参数,根本不用去 UI 里"清默认预选"那一套**(那是 DOM 路径才有的坑)。`extraStr.quickFilter` 是 Boss 给的建议筛选 chips,可留空/忽略。
- **响应**:`zpData.geeks[]`(**注意 key 是 `geeks` 不是 `geekList`**)+ `zpData.hasMore`(翻页)。搜索结果是**打码候选人**(`geekCard.name` 形如 `"S**"`)。
- **每个候选人**:`geekCard{ name(打码), gender, city, workYear, salary/lowSalary/hightSalary, geekDesc(优势), degreeName, current(当前公司/职位), expect(期望), encryptExpectId, securityId }` + 顶层 `friendRelationStatus`(**搜索通道的去重标**,是否已建立关系/联系过)、`geekCallStatus`、`read`、`works`、`ageDesc`。
- **⚠ 触达搜索结果要花畅聊卡**(打码人,开聊=3卡+捆绑索要PII,见 §2B);接口只负责**免费拉列表/筛选**,真要触达仍走 UI 开聊(有确认+境外提示等门)。

### 🟢 搜索候选人详情(geek/info)—— 破 canvas 反爬,读全文简历(2026-07-07 实测)
点搜索结果卡看简历详情有一整套**反爬**:卡片 `<a ka=search_click_open_resume>` 用 JS 在**新标签页**打开、简历画在 **`<canvas>`** 上(伴随 `static.zhipin.com/.../wasm/resume/wasm_canvas_bg.wasm`)——**DOM 读不到文字、browser-act 跟不到新标签、eval-click 触发不了、干净截详情页也做不到**。**但接口层直接破了它**:
`GET /wapi/zpitem/web/boss/search/geek/info?securityId={该候选人的 geekCard.securityId}&query={关键词}&encryptGeekDetailGray=1`
- **securityId 自足**:从上面 `geeks.json` 响应里**每个候选人的 `geekCard.securityId`** 直接取(**不用抓包**;实测 ~1148 字符)。→ 即"搜索列表用 geeks.json,读某人详情用 geek/info",端到端接口,不碰脆弱 DOM。
- **响应 `zpData.geekDetail` 是明文结构化 JSON**(同响应里的 `encryptGeekDetail`/`wasm` 只给 canvas 渲染用;明文 `geekDetail` 直接可读):
  - `geekBaseInfo`{ name(打码), ageDesc, workYearDesc, degreeCategory, applyStatusContent(求职状态), activeTimeDesc, **userDescription(个人优势全文)** }
  - `geekExpectList[]`{ locationName, positionName, salaryDesc, industryDesc }(求职意向,可多条)
  - `geekWorkExpList[]`{ startYearMonStr, endYearMonStr, company, positionName, department, **responsibility(工作职责全文)**, workPerformance(业绩) }
  - `geekProjExpList[]`(项目)、`geekEduExpList[]`{ school, major, degreeName, eduType, thesisTitle, courseDesc, majorRankingDesc }、`professionalSkill`、`resumeSummary`、`highlightWords`、`certList` 等。
- **⚠ 纯只读**:geek/info 拉详情=免费、零外发、零红线;真要联系仍走 UI 开聊(3卡+PII捆绑,红线)。
- **导出简历 markdown**:遍历各 `*List` 模块 → 基本信息/求职意向/个人优势/工作经历/教育 分节拼 md,比截图 OCR 干净准。**这是"批量读搜索候选人详情 / 转简历文档"的主路径**(截图只能截搜索结果卡,详情画布截不到)。

### 🔴 会话/消息列表 = WebSocket(没有干净 REST)
- `GET /wapi/zpitem/web/chat/message/list/box` 实测只是**通知盒摘要**(单对象 showBox/title/messageInfo),**不是会话列表**。
- 真正的会话列表和消息走 **WebSocket 实时推送**,没有可直接 GET 的 REST 端点 → **会话/回执类去重只能读 DOM 漏斗(§7c 扫回执),或用推荐接口的 `haveChatted` 标(更省事)**。

## 7f. ✅ 全局去重(2026-07-06,防 24h 重复触达风控)
触达前判"这人是不是已经接触过",两个来源:
1. **接口内建标(首选,Boss 官方口径最准)**:推荐通道 `rec/geek/list` 里 `haveChatted==1` 或 `isFriend==1`;搜索通道 `geeks.json` 里 `friendRelationStatus`(已建立关系/联系过)或 `geekCallStatus`。命中 → 已接触,**直接 skip、别再触达**。
2. **账本交叉比对(跨通道/搜索/inbound)**:对接口没给 haveChatted 的人(如搜索命中的打码人),用 ledger 里 `status∈{greeted,chatted,replied,resume_received,contact_exchanged}` 的人做匹配:键=`(geekName 或打码名前缀) + 最近公司 + 期望`,相似即判重复(打码名↔真名可能同一人,命中标 `possible_dup` 人工确认)。
3. ledger 建议加 `last_touched_date` 字段,配合"同一人 24h 内不重复触达"的软规则。
**为什么要紧**:同一候选人短时被多次打招呼(跨策略/跨同事)极易触发爬虫风控,还砸雇主品牌——这是 silent killer。
- **实战侧记**:候选人A(示例)(初判弱匹配)收到求简历后**发来附件简历**并在回复里补充了履历上看不到的语音实战(asr/vad/tts/kws 均做过)——实际比履历显示的更对口,说明**对话探询能挖出履历外的匹配信息**,是筛选环节的价值点。

## 8. 进度清单

**已跑通(2026-07-03)**:
- [x] 牛人搜索 + 筛选 + 简历详情翻页/截图
- [x] 搜索畅聊卡开聊(消耗畅聊卡)
- [x] 发布职位(完整流程)
- [x] 推荐牛人「打招呼」(走标准额度不扣畅聊卡;**日限 200 沟通**)
- [x] 会话内回复消息
- [x] 会话内求简历(「确定向牛人索取简历吗?」确认框)
- [x] 换电话 /换微信 确认框(「确定与对方交换手机/微信吗?」,已验证结构未实发)
- [x] 账号权益 / 招聘数据 / 工具箱 / 自定义打招呼语(只读+配置项已记录)
- [x] XHR 接口层核心端点(rec/geek/list 等)
- [x] **推荐通道接口主路径**(rec/geek/list 全参数+响应结构+haveChatted去重标+hasMore翻页,2026-07-06 实测,见 §7e)
- [x] **全局去重**(接口 haveChatted/isFriend + 账本交叉比对,2026-07-06,见 §7f)
- [x] **搜索页默认预选清除**三件套选择器(关键词/职位/城市,2026-07-05,见 §2B)
- [x] **健康检查读法**(每日打招呼额度 X/200 + 畅聊卡余量,2026-07-05,见 §7d)
- [x] **扫回执机制**(沟通中 tab + status 信号 → full 档异步求简历闭环,2026-07-05,见 §7c)

**待补**:
- [ ] 会话内**约面**(`.interview`「约面试」)发起流程 —— 一级第④项,唯一没跑的核心动作(用户暂缓;红线不自动但操作待文档化)
- [ ] 自定义打招呼语的**实际设置**(设置页选择器已只读补录 §7d,2026-07-06;写路径=账号级持久配置,等用户定措辞再走,agent 默认只读不写)—— 注意管线定制招呼语已有替代路径(§11.1 会话内补发),此项只影响系统默认语
- [x] **搜索通道接口化**(geeks.json 全参数+响应结构+friendRelationStatus去重标,2026-07-06 实测,见 §7e🟢;接口直接传干净keywords,免掉清默认坑)
- [ ] 会话/消息发送 = WebSocket,无干净 REST(§7e🔴);回执类去重走 DOM 漏斗或推荐接口 haveChatted
- [x] 招聘运营直觉框架(定制招呼语 / 反馈环 / 薪资破格 / 花卡预判)—— 已落地为可选开关,见 playbook §11(默认关,逐个 enabled 启用);真机整轮实测待补

---

## 附:招聘循环的落地形态(基于本地图)

```
一次性资料:产品/业务介绍 + 岗位JD + 话术库(常见问答/薪资范围/红线)
每日循环(agent):
  推荐牛人扫一遍 → 匹配打分 → 报今日名单 →(确认/规则内)打招呼   [通道A,免费优先]
  推荐不足时 → 搜索精准定向 →(报畅聊卡消耗+确认)畅聊             [通道B,付费]
  盯沟通页/牛人管理漏斗 → 常规问题按话术库草拟 →(确认)回复
  敏感问题(谈薪/期权/竞对)→ 升级给人
  拿到简历 → 归档+生成摘要 → 提议面试时间 →(面试官确认)约面 → 面试日历
```
