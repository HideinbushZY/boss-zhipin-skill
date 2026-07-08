---
name: boss-zhipin
description: "Boss直聘招聘者侧网页操作 + 策略驱动寻访引擎。两类触发:(A) 单点操作——搜索候选人/看推荐牛人、读简历、打招呼、搜索畅聊、回复消息、求简历、查招聘数据/账号权益/牛人管理漏斗(换电话/换微信/约面/删除职位=永久红线只导航;关闭/发布职位=agent 可代操作,发布须提交前回读锁死字段+不买曝光);(B) 给一段搜索策略(JD/目标公司职位/人选能力要求)让它自动找人筛人触达并反馈——此时按 playbook.md 跑寻访管线。通过 browser-act 接管已登录的真实 Chrome(chrome-direct)执行。触发后先读 operation-map.md(怎么点页面)+ playbook.md(策略怎么跑)。"
allowed-tools: Bash(browser-act:*), Bash(python3:*), Read, Write, Edit
metadata:
  author: (packaged as a reusable skill)
  version: "1.0"
  updated: "2026-07-04"
  homepage: "基于 browser-act(browseract.com)"
  requires:
    - "browser-act CLI 已安装并配好 API key"
    - "一个已登录的 Boss直聘招聘者账号,通过 chrome-direct 接管"
  validated: "已用全新 agent(无上下文,仅凭本 skill)实测独立跑通搜索→打开候选人详情"
---

# boss-zhipin

让 agent 丝滑操作 Boss直聘招聘者工作台。两层能力:
- **操作层**:怎么点每个页面(`operation-map.md`,全部实测)。
- **寻访引擎**:用户给一段搜索策略 → 判定单次/心跳 → 找人[推荐/互动/搜索]→ LLM 打分 → 触达 → 报告(`playbook.md`)。把招聘侧免费杠杆用到极致,状态落本地账本增量运行。

## 两种用法

- **单点操作**("帮我搜X/给谁打招呼/发个岗位/把这批人简历导markdown/**给你几份合适简历找类似的人**"):读 `operation-map.md`,直接按选择器/接口操作。"以人找人"(样本简历→相似候选人,只读)见 §7h;"导简历markdown"见 §7g。
- **策略寻访**("按这个 JD/从这几家挖某类人/找具备X能力的人,帮我找"):读 `playbook.md`,把策略解析成 `strategies/<name>/strategy.yaml`,跑单轮管线(找→筛→触达→报告),状态写 `strategies/<name>/ledger.jsonl`,报告落 `reports/`。示例策略见 `strategies/asr-engineer-example/`。

## 用前必做(3 步)

1. **读同目录 `operation-map.md`** —— 完整页面地图、找人两通道、候选人漏斗状态机、成本额度、各流程选择器与确认框、踩坑速查、进度清单。这是本 skill 的核心。
2. **换成你自己的浏览器 id**:`browser-act browser list` 查你的 chrome-direct 浏览器 id,**替换 operation-map 全文的 `<YOUR_BROWSER_ID>` 占位符**(注意 `<YOUR_BROWSER_ID>` 是占位符、不是可用 id,必须替换)。若还没有 chrome-direct 浏览器,先 `browser-act get-skills advanced` 按引导创建。
3. **确认登录**:先开会话打开工作台——`browser-act --session <名> browser open <你的浏览器id> https://www.zhipin.com/web/chat/index --headed`;再 `browser-act --session <名> eval "document.querySelector('.user-name')?.textContent"` 应返回招聘者姓名(没开会话/页面不在 zhipin.com 时这条 eval 拿不到值)。

## 四条操作铁律(最容易踩错,踩了就失败/返工/发错人)

- **读用 eval,点击/输入用 browser-act 索引**:`eval "...contentDocument..."` 只用来**读** DOM(同源,比截图快一个量级);**点击/输入必须走 `state` → 取 `[索引]` → `click <索引>` / `input <索引>`**(真实手势)。eval 的 `element.click()` 往往打不开详情弹层/模态框。文中 CSS 选择器只是帮你在 state 里认元素,不是让你 querySelector 后 eval-click。
- **发消息前必核收件人**:会话列表是筛选页签作用域的(切页签后目标可能不在列表,eval 找人会静默失败,当前会话停在上一个人)。发送前 `eval` 读聊天区头部 `.name-container .name-box` **必须等于目标姓名**,内容核验≠收件人核验——真实踩过把 A 的消息发给 B(operation-map §7c 三验)。
- **聊天页(`/web/chat/index`)冷加载直达 URL 会卡死在"加载中"**,必须从**左菜单点「沟通」进入**(应用内路由)才正常。重启 Chrome 后尤其注意。
- **搜索页(`/web/chat/search`)打开时有默认预选**(职位 + 城市 + 热门词关键词,并自动出"根据热门词…"结果)。做干净的主动搜索前**必须先清空这些默认**,否则结果被残留的默认职位/城市污染,搜出不想要的人。

## 安全门(硬规则,不可越)

- **单点操作模式**:外发内容(打招呼/发消息/求简历)、关闭职位、发布职位、消耗权益(畅聊卡/道具)→ 发出前逐条向用户确认(关闭须先核对是哪个岗;发布须回读 4 个锁死字段+内容)。用户点名要求红线动作(换电话/约面/删除职位等)时同样:agent 只导航到位、给步骤,确认/发送那一下由用户亲自点。
- **策略寻访模式**:外发按策略的 `touch_policy` 档执行(`report_first` 零外发 / `greet_*` 自动打招呼 / `full` 自动打招呼 + **回复后**求简历),消耗畅聊卡按 `budget.chat_cards` 逐张记账、超预算停。用户在 strategy.yaml 里授权,即视为该策略的持续授权。
  - **⚠ full 档"求简历"有平台前置门**:求简历按钮在候选人回复前是 disabled,平台层禁用;所以 full 不是"打招呼当下顺手求简历",而是 **打招呼 → 候选人回复 → 求简历** 两拍,未回时标 pending-reply、待下轮扫回执再补(详见 operation-map §7c、playbook §5)。
  - **⚠ 搜索畅聊卡"开聊"= 消耗畅聊卡(逐人 1~3 张,读 `searchChatCardCostCount`,非固定3)+ 自动"索要简历/微信/电话"捆绑**(内置换微信/换电话的 PII 请求)。用畅聊卡等于触发这个捆绑——建策略/授权 `budget.chat_cards>0` 前须让用户知情并接受(成本/余量/流程详见 operation-map §2B/§7i)。
- **永久红线(任何模式、任何档位都不自动)**:换电话 / 换微信 / 约面 / **删除职位** / 举报 / 批量标记不合适 —— 这些最深的 PII/承诺/**不可逆**破坏性动作只在报告里给建议,等人来点。
- **关闭职位(可操作,发出前确认 + 核对岗位)**:关闭是**可逆**动作(进「已关闭」页签,可「重新开放」,候选人对话/简历保留),故不列永久红线——agent 可代关。硬门三条:①**先核对是哪个岗位**(读职位卡标题=目标岗,防误关别的在招岗,同"发消息核收件人"铁律)②关前向用户确认"关这个岗、其沟通/简历随岗归入已关闭"③点关闭后验证该岗进入「已关闭」。
- **发布职位(可操作,提交前须确认内容 + 不买曝光)**:发布是**对外公开**动作、且**招聘类型/职位名称/职位类型/工作城市 发布后永久锁死**(经验/薪资等可改)——故不全自动,但 agent 可代填整张向导并提交。硬门三条:①那 4 个锁死字段 + JD 内容**提交前回读给用户确认**(用户拍板内容=授权,不是无关地再问一遍)②agent 只填向导/点提交,岗位内容由用户定 ③发布成功后会弹**付费曝光升级推销,只关不买**(付费=红线)。**删除仍是唯一永久红线(不可逆);发布/关闭均可代操作。**
- **低频、限速、分批**:招聘方账号有行为风控,短时高频自动化会触发软限制(账号是公司资产)。命中疑似风控就停手等冷却,不要连续重启 Chrome(每次重启还可能触发登出,登出需用户手机扫码,agent 代替不了)。
- 每次任务结束 `browser-act session close <名>` 释放 Chrome。

## 更稳的路子(可选)

DOM 选择器会随 Boss 改版腐烂。若做批量/长期自动化,优先用抓到的 **XHR 接口层**(如推荐列表 `GET /wapi/zpjob/rec/geek/list?jobId={encryptId}&page=N&{筛选}`,见 operation-map §7e),接口比选择器稳得多。

## 覆盖范围

核心**寻访**闭环(发岗位→找人[推荐/搜索,接口主路径]→LLM打分→触达[打招呼/畅聊卡开聊]→沟通[回复]→求简历)已真账号实测跑通(7轮)。**边界(别当"完整招聘闭环"):闭环止于"收到简历";换电话/微信=永久红线不自动**(畅聊卡开聊会平台捆绑索要简历/微信/电话,故 `chat_cards>0` 须显式 `authorize_card_pii_bundle: true`,validate.py 强制);**约面未实测**(红线不自动)。运营智能层四功能逻辑已用真实数据验证、但未真实外发。**触达两条路**:①**走量**——推荐通道免费扫合格池群发(§7j);②**定点某个/某几个指定的人**——搜索通道定点法(清污染 jobId=0 + 该人独特关键词精准置顶 → UI 开聊,§7i;已开聊者会自动从搜索隐藏)。页面改版后需重新验证选择器(接口层比 DOM 抗腐烂)。
