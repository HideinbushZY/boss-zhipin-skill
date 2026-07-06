# 浏览器后端:browser-act 与可替代方案

> 本 skill 默认用 **browser-act(chrome-direct)** 驱动浏览器。它够用、且在真实 Boss 账号上实测跑通多轮。但它**核心闭源**(CLI 经 PyPI 分发)、**要注册配 API key**、社区偏小——所以有人问"能不能换个免费/开源的"。
> 这份文档给出:① skill 对浏览器后端的**能力契约**(换任何工具都要满足);② 候选替代的**实测结论**(2026-07-06 在真机上验证过,不是纯查文档);③ **动词映射表**,真要换时照着改。

## 一、能力契约(5 项,缺一不可)

任何替代 browser-act 的工具,必须能:

1. **接管用户"真实已登录"的 Chrome** —— Boss 登录=手机扫码,agent 代替不了;风控绑定真实指纹;且 **Chrome 136+ 禁止对默认 user-data-dir 开调试端口**,不能靠重启 Chrome 加参数(重启可能登出、不可逆)。
2. **受信手势(`isTrusted=true`)** —— 点击/输入必须是 CDP Input 级真实手势。**实测:eval 的 `element.click()` 打不开 Boss 的详情弹层/模态框**,只有受信点击能开(operation-map §0 铁律的根)。要覆盖 contenteditable 输入 + `cmd+a`/`Backspace` 组合键。
3. **页面上下文同源 JS** —— 读 DOM(含同源 iframe `contentDocument`)+ **同源 sync XHR 调 Boss 内部接口**(`rec/geek/list`、`geeks.json` = 现在的找人主路径)。
4. **网络抓包(URL 级)** —— 低频,唯一刚需是抓 `encJobId`;只要请求 URL 列表,不需响应体/拦截。
5. **会话 attach/detach 不杀 Chrome + 显式 tab 选择**(防焦点漂移到误开的新标签)。

## 二、候选替代 · 实测结论(2026-07-06 真机)

| 工具 | 协议/成本 | 契约覆盖 | 实测到的关键事实 |
|---|---|---|---|
| **browser-act**(默认基准) | 闭源核心 + 免费层 + 付费云,要 API key | 6/6 | 本项目多轮真实 Boss 寻访**一次接上**;`230404` 偶发断连(云控制面依赖) |
| **chrome-devtools-mcp**(Google) | Apache-2.0,**全免费官方** | 5.5/6 | **实测 `isTrusted=true` 受信点击 ✓、同源 sync XHR ✓**(受控实例);接管真实 Chrome 需 **Chrome 144+ 在 `chrome://inspect` 手动勾"允许远程调试"**(免重启) |
| **Playwright CLI/MCP + 扩展**(微软) | Apache-2.0,**免费开源** | 6/6(机制) | 工具齐 ✓;**实测扩展 relay 能接上真实 Chrome**(抓到 Chrome↔server socket);但**装配摩擦大**(见下"诚实警告") |
| **claude-in-chrome**(Anthropic 官方) | 对 Claude Code 订阅用户**零新增依赖** | 6/6 | `javascript_tool` 页面上下文 + await ✓;仅限直连付费计划,**不支持 Bedrock/Vertex/WSL** |
| **mcp-chrome**(hangwin) | MIT,**纯开源零账号** | 6/6(需锁 CDP 路径) | 网络抓包最强(带响应体);但**单人维护、约半年无提交**,扩展要开发者模式装 |
| **agent-browser**(Vercel) | Apache-2.0,免费 | 5/6 | token 效率最佳;但 Chrome 136-143 默认 profile 下 `--auto-connect` 失效,144+ 需手动开关 |

## 三、🔴 诚实警告:扩展路线"能力对等 ≠ 装配更省事"

2026-07-06 实测把 Playwright 扩展接上真实 Boss Chrome,为接上一条 relay 连续踩了:

- **token 会轮换**——扩展重新生成后,服务器上的旧 token 对不上,relay 认证失败;
- **relay 默认绑 IPv6**(`ws://[::1]:port`)→ 扩展连它直接 `Connection timeout`,必须 `--host 127.0.0.1` 强制 IPv4;
- **每个 MCP 会话都要手点一次"连接"** + 选标签页;会话绑定不跨进程复用;
- 失败重试会**留下一堆空标签页**。

**对照**:browser-act 的 chrome-direct 在本项目里两次真实寻访**一次就接上**。

> **结论**:扩展路线(Playwright / claude-in-chrome / mcp-chrome)**机制齐备、能力对等、且结构上绕开了 Chrome 136+ 的端口封锁**(用 `chrome.debugger` 不碰调试端口),**但首次装配摩擦并不比 browser-act 低**。它们的真正卖点是 **免费 / 开源 / 无 API-key 依赖**,不是"更丝滑"。按你在意的维度选:想去掉付费/闭源依赖 → 换;只图省事 → browser-act 已经够顺。
>
> 且:**别像"从 shell 手搓 MCP 客户端"那样用它们**——那样会撞上 token/relay/会话绑定一堆坑。正确姿势是**把它配成 MCP client(如 Claude Code)的原生 MCP server**,由 client 自动编排 token/relay/会话持久化。

## 四、动词映射表(真要换时照改)

| browser-act | 语义 | Playwright MCP | claude-in-chrome | chrome-devtools-mcp |
|---|---|---|---|---|
| `browser open <id> <url>` | attach 已登录 Chrome | `--extension`(配成原生 MCP) | `/chrome` 配对 | `--browser-url`(Chrome144+ chrome://inspect) |
| `state` → `[索引]` | 可交互元素+句柄 | `browser_snapshot`(uid) | `read_page`/`find`(ref) | `take_snapshot`(uid) |
| `click <索引>` | 受信点击 | `browser_click(ref)` | `computer left_click(ref)` | `click(uid)` |
| `input <索引>` | 受信输入(含 contenteditable) | `browser_type` | `form_input` | `fill` |
| `keys "cmd+a"` | 组合键 | `browser_press_key` | `computer key` | `press_key` |
| `eval "..."` | 页面上下文 JS(读 DOM+sync XHR) | `browser_evaluate` | `javascript_tool` | `evaluate_script` |
| `network requests` | XHR 抓包 | `browser_network_requests` | `read_network_requests` | `list_network_requests` |
| `screenshot` | 截图兜底 | `browser_take_screenshot` | `computer screenshot` | `take_screenshot` |
| `session close` | 释放,不杀 Chrome | `browser_close` | tab 关闭 | `close_page` |

> **注意**:四条操作铁律(读用 eval、点用受信手势、聊天页走菜单、发消息前核收件人)**与后端无关**,换任何工具都原样成立——铁律讲的是 Boss 页面的行为约束,不是 browser-act 的特性。

## 五、迁移建议

- **想去掉 API-key/闭源依赖**:首选 **Playwright CLI + 扩展**(免费、开源、CLI 形态改写成本最低)或 **claude-in-chrome**(Claude Code 用户零新增依赖)。配成**原生 MCP server**,别手搓。
- **改写面**:`SKILL.md` 的 `allowed-tools`、`operation-map.md §0` 命令表、全文内联命令;若新工具用 uid/ref 而非数字索引,"state→索引→click"的表述要整段改,但受信手势 vs 只读 eval 的二分法保留。
- **首个换后端的人**:欢迎把你那条链路的实测坑提 PR 补进本表(见 CONTRIBUTING)。
