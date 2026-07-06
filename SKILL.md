---
name: boss-zhipin
description: "Boss直聘招聘者侧网页操作 + 策略驱动寻访引擎。两类触发:(A) 单点操作——搜索候选人/看推荐牛人、读简历、打招呼、搜索畅聊、回复消息、求简历/换电话/换微信、发布或管理职位、约面、查招聘数据/账号权益/牛人管理漏斗;(B) 给一段搜索策略(JD/目标公司职位/人选能力要求)让它自动找人筛人触达并反馈——此时按 playbook.md 跑寻访管线。通过 browser-act 接管已登录的真实 Chrome(chrome-direct)执行。触发后先读 operation-map.md(怎么点页面)+ playbook.md(策略怎么跑)。"
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

- **单点操作**("帮我搜X/给谁打招呼/发个岗位"):读 `operation-map.md`,直接按选择器操作。
- **策略寻访**("按这个 JD/从这几家挖某类人/找具备X能力的人,帮我找"):读 `playbook.md`,把策略解析成 `strategies/<name>/strategy.yaml`,跑单轮管线(找→筛→触达→报告),状态写 `strategies/<name>/ledger.jsonl`,报告落 `reports/`。示例策略见 `strategies/asr-engineer-example/`(账本文件是 ledger.example.jsonl,真跑时改名为 ledger.jsonl)。

## 用前必做(3 步)

1. **读同目录 `operation-map.md`** —— 完整页面地图、找人两通道、候选人漏斗状态机、成本额度、各流程选择器与确认框、踩坑速查、进度清单。这是本 skill 的核心。
2. **换成你自己的浏览器 id**:`browser-act browser list` 查你的 chrome-direct 浏览器 id,**替换 operation-map 全文的 `<YOUR_BROWSER_ID>` 占位符**(原作者机器上的实际 id 是 `direct_local_YOUR_BROWSER_ID`,不通用)。若还没有 chrome-direct 浏览器,先 `browser-act get-skills advanced` 按引导创建。
3. **确认登录**:`browser-act --session <名> eval "document.querySelector('.user-name')?.textContent"` 应返回招聘者姓名。

## 三条操作铁律(最容易踩错,踩了就失败/返工)

- **读用 eval,点击/输入用 browser-act 索引**:`eval "...contentDocument..."` 只用来**读** DOM(同源,比截图快一个量级);**点击/输入必须走 `state` → 取 `[索引]` → `click <索引>` / `input <索引>`**(真实手势)。eval 的 `element.click()` 往往打不开详情弹层/模态框。文中 CSS 选择器只是帮你在 state 里认元素,不是让你 querySelector 后 eval-click。
- **聊天页(`/web/chat/index`)冷加载直达 URL 会卡死在"加载中"**,必须从**左菜单点「沟通」进入**(应用内路由)才正常。重启 Chrome 后尤其注意。
- **搜索页(`/web/chat/search`)打开时有默认预选**(职位 + 城市 + 热门词关键词,并自动出"根据热门词…"结果)。做干净的主动搜索前**必须先清空这些默认**,否则结果被残留的默认职位/城市污染,搜出不想要的人。

## 安全门(硬规则,不可越)

- **单点操作模式**:外发内容(打招呼/发消息/求简历)与消耗权益(畅聊卡/道具)→ 发出前逐条向用户确认。
- **策略寻访模式**:外发按策略的 `touch_policy` 档执行(`report_first` 零外发 / `greet_*` 自动打招呼 / `full` 自动打招呼 + **回复后**求简历),消耗畅聊卡按 `budget.chat_cards` 逐张记账、超预算停。用户在 strategy.yaml 里授权,即视为该策略的持续授权。
  - **⚠ full 档"求简历"有平台前置门**:求简历按钮在候选人回复前是 disabled,平台层禁用;所以 full 不是"打招呼当下顺手求简历",而是 **打招呼 → 候选人回复 → 求简历** 两拍,未回时标 pending-reply、待下轮扫回执再补(详见 operation-map §7c、playbook §5)。
  - **⚠ 搜索畅聊卡"开聊"= 消耗 3 张卡 + 自动"索要简历/微信/电话"捆绑**(内置换微信/换电话的 PII 请求)。用畅聊卡等于触发这个捆绑——建策略/授权 `budget.chat_cards>0` 前须让用户知情并接受(详见 operation-map §2B)。
- **永久红线(任何模式、任何档位都不自动)**:换电话 / 换微信 / 约面 / 发布·关闭·删除职位 / 举报 / 批量标记不合适 —— 这些最深的 PII/承诺/破坏性动作只在报告里给建议,等人来点。
- **低频、限速、分批**:招聘方账号有行为风控,短时高频自动化会触发软限制(账号是公司资产)。命中疑似风控就停手等冷却,不要连续重启 Chrome(每次重启还可能触发登出,登出需用户手机扫码,agent 代替不了)。
- 每次任务结束 `browser-act session close <名>` 释放 Chrome。

## 更稳的路子(可选)

DOM 选择器会随 Boss 改版腐烂。若做批量/长期自动化,优先用抓到的 **XHR 接口层**(如推荐列表 `GET /wapi/zpjob/rec/geek/list?jobId={encryptId}&page=N&{筛选}`,见 operation-map §7d),接口比选择器稳得多。

## 覆盖范围

核心招聘闭环(发岗位→找人[推荐/搜索]→触达[打招呼/畅聊]→沟通[回复]→收简历→换联系方式)已实测跑通;**约面、搜索页默认预选的确切清除步骤等为待补**(见 operation-map §8 进度清单)。页面改版后需重新验证选择器。
