# boss-zhipin — Boss直聘招聘者侧操作 + 策略驱动寻访引擎(可复用 skill)

> A reusable Claude skill that turns an agent into a Boss直聘 (Chinese recruiting platform) **recruiter-side** operator: it drives a real logged-in Chrome to search/greet/screen candidates, and runs a strategy-driven sourcing pipeline (parse JD → find → LLM-score → reach out → report) with a local ledger for incremental runs. All page maps and selectors were verified by live operation on a real account.

一个可复用的 Claude skill:让 agent 像 **Boss直聘招聘者侧的熟手** 一样操作工作台,并把一段"搜索策略"跑成 `解析→找人→打分→触达→报告` 的自动寻访管线。页面地图和选择器全部真机实测过。

---

## 这是什么 / 三层结构

| 文件 | 层 | 作用 |
|---|---|---|
| **SKILL.md** | 触发头 | 什么时候用、三条操作铁律、安全门(红线)。你的 agent 先读它。 |
| **operation-map.md** | 执行层 | 每个页面怎么点、全部实测选择器、踩坑速查、健康检查/扫回执/清默认等确切步骤。 |
| **playbook.md** | 编排层 | 把策略解析成配置 → 找人[推荐/搜索/互动] → LLM 打分 A/B/C → 按档触达 → 落报告。 |
| **strategies/asr-engineer-example/** | 示例 | 一个填好的策略样例:`strategy.yaml`(配置)+ `ledger.example.jsonl`(账本 schema)+ `reports/`(报告格式)。**均为脱敏示例数据,非真实候选人。** |

---

## 用前提(prerequisites)

1. **browser-act CLI**(BrowserAct 家的浏览器自动化 CLI):`uv tool install browser-act-cli`,并配好 API key。skill 靠它接管你本机已登录的真实 Chrome。
   - 也可换成任何"能接管已登录 Chrome、能读 DOM + 真实点击"的等价工具;文中命令是 browser-act 语法,选择器/流程是通用的。
2. **一个已登录的 Boss直聘招聘者账号**,通过 browser-act 的 **chrome-direct**(接管本机 Chrome)访问。企业招聘者身份(能发职位/看推荐牛人/搜索牛人)。
3. Claude(或同类)agent 作为大脑跑 playbook 的判断/打分。

## 装配(3 步,照 SKILL.md「用前必做」)

1. 把 `boss-zhipin/` 整个文件夹放进你的 skills 目录(如 `~/.claude/skills/boss-zhipin/`),或直接让 agent 读 `SKILL.md` 入口。
2. **换浏览器 id**:`browser-act browser list` 查你自己的 chrome-direct id,**替换 operation-map 全文的 `<YOUR_BROWSER_ID>` 占位符**。若还没有 chrome-direct 浏览器,`browser-act get-skills advanced` 按引导建。
3. **确认登录**:`browser-act --session <名> eval "document.querySelector('.user-name')?.textContent"` 应返回你的招聘者姓名。

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
- **接口层(XHR)**只抓了推荐侧;做批量/长期自动化建议接接口作主路径、DOM 抓取降为 fallback(抗改版)。
- **招聘运营直觉**基本没有:打招呼零个性化(系统模板)、无最佳时段、超带一刀切没有"稀缺该破格加薪"的两维权衡、无跨轮全局去重(24h 重复触达=风控隐患)、无当日回复率反馈环。**这是"会点按钮"和"懂招聘经营"的差距。**
- 页面改版后选择器会腐烂,需重新验证。

**边界**:定位是"单次 + 单岗策略引擎"。不含:定时心跳持续运行、群发、offer/入职跟踪、与外部 ATS/HRIS 集成。

---

## 隐私说明

本包内示例策略的 `ledger.example.jsonl` 与 `reports/` **全部是虚构脱敏数据**;core 文档里的账号/公司/招聘者/地址/邮箱/真实候选人姓名均已抹除或换成占位符。真机跑出来的候选人数据请自己妥善保管、勿外发(涉及求职者个人信息)。
