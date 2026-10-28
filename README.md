# 撸西西的本地工作台 · Luxixi Local Workbench

**用自己的 AI 客户端做 SEO，结果回到自己的本地工作台。**  
**SEO workflows powered by your own AI client, with results saved to your local workbench.**

[中文](#中文) · [English](#english) · [Compatibility](COMPATIBILITY.md) · [MIT License](LICENSE)

> **0.6.1 预览版 / Preview.** 已验证 Windows 隔离安装与本地数据流程。Mac 实机、Claude 原生端到端、自然定时触发及真实 Google 接入仍待完整验证。请按[兼容矩阵](COMPATIBILITY.md)判断实际支持，不按模型品牌推定兼容。

## 中文

### 这是什么

一个可安装到 **Codex 或 Claude Code 项目工作区**的 Skill，加上一套只监听本机的网页工作台。安装、网站接入和执行引导在 AI 聊天里进行；工作台集中展示网站数据、检查报告、工单和获准扫描的 Skill。

使用安装者自己的客户端订阅和 Google 授权，不内置模型、不接模型计费网关，也不要求模型 API Key。安装后从独立空库开始，不携带开发者的网站、数据库、账号、聊天或测试排期。

### 功能

| 功能 | 用户能做什么 |
| --- | --- |
| **SEO 工作台** | 按站点查看搜索表现与访问统计，独立选择近7天/30天/当前可用历史窗口，查看数据日期、缺口和趋势；GSC与GA4分开，缺失不填零。 |
| **聊天式接入** | 在当前聊天提供网站、名称、目标和语言市场；复用已给信息，新增网站继续使用原工作台。源码目录可选。 |
| **自己的 Google MCP** | 复用或引导安装者配置只读 Search Console/GA4 工具，分别核权限、站点匹配及实际读取。Google登录由本人完成。 |
| **有限只读检查** | 首次抽查首页、robots、默认sitemap；后续巡检最多6个页面并检查标题、描述、canonical、noindex、重定向/404及主域/www等。Google索引记录单独呈现，HTTP正常不代表已收录。 |
| **同库工单** | 看问题与证据，复制执行提示给自己的AI；实际领取后处理、验证并回写同一库。旧修订、并发、重复粘贴和结果不明都有核对流程，复制本身不开始执行。 |
| **周期与效果复查** | 用户明确要求后，使用客户端实际可用的原生持久机制配置一项统一任务；新增网站复用。效果复查关联原优化记录和真实上线时间，按7/15/30天窗口处理；缺数据继续观察，不保证排名或因果。 |
| **方法研究** | 在同一周期复查官方资料与开源候选，记录版本、来源、许可和验证状态；保留最近完整结果，不自动安装或融合陌生代码。 |
| **自动化 Tab** | 展示已接入本库的任务、最近运行、下次时间、异常与实际回执。当前仅有统一SEO任务投影，不自动扫描电脑上的全部任务。 |
| **Skill Tab** | 只扫描用户选定目录中的技能元数据，按用途分类、搜索，显示来源/版本/启用状态；发现不等于允许执行。 |
| **本地运行与恢复** | 页面服务关闭浏览器后仍可运行，记录保留在本机；Windows提供固定入口、显式登录启动管理及保留数据卸载。 |

### 开始使用

需要可运行本机命令的 AI 客户端、已有 Python 3.10+ 和下载固定依赖所需的网络。实际安装验证使用 Windows 11 / Python 3.12.10，其他组合见矩阵。普通网页或云会话没有本机连接时，不能直接安装或访问本机记录。

1. 下载本仓库的 ZIP 并解压，或克隆仓库。在 Codex / Claude Code 中打开自己选定的工作区，让 AI 读取 `luxixi-workbench/SKILL.md`，按它引用的安装说明操作。
2. 安装到该工作区的项目级 Skill 目录。只选择实际使用的客户端；不会修改用户级 Skill、MCP 或全局 Python 配置。
3. 运行初始化，选择独立数据目录；记住返回的实际服务地址与数据目录，后续始终复用它。
4. 在聊天提供网站并完成只读 Google 接入，进行首次检查，再打开工作台看结果。没有 Google 也可先检查公开页面，缺口明确显示。

安装命令示例（替换成自己选择的绝对路径）：

```text
# Codex；Claude Code 将最后一个参数改为 claude
python -X utf8 <仓库目录>/luxixi-workbench/scripts/install_skill.py --workspace <工作区绝对路径> --client codex
```

在**已安装的 Skill 目录**中初始化：

```text
python -X utf8 scripts/workbench.py setup --data-dir <独立数据目录绝对路径>
```

Mac 上若命令名是 `python3`，使用已有的 `python3`；这不代表 Mac 已通过实机验收。可选 `--port` 设置端口；端口占用时不会接管其他服务。

项目级安装后，在 Codex 调用 `$luxixi-workbench`，在 Claude Code 调用 `/luxixi-workbench`。客户端仍需实际加载 Skill 并获得相应本机工具权限。

### 新用户旅程

**安装 Skill → 在聊天提供网站 → 本人授权 Google → 完成只读初检 → 打开本机工作台 → 按需开统一巡检 → 复制工单给 AI → 验证并写回。**

第一次打开工作台只有自己的空库和接入状态。三个 Tab 依次为 **SEO、自动化、Skill**。如果没授权扫描目录，Skill列表暂时为空；没配置排期，自动化列表不会伪造任务。`/demo/` 是明确标记的内存合成演示，不向真实库填充数据。

页面每30秒读取本地记录，不会每30秒向Google取数或执行SEO。安装不会自动建立排期；定时任务需要用户明确要求且客户端具备实际能力。暂停/取消不恢复，所有站点共用一项统一任务。

### Google 接入

工作台不收集 Google 密码、令牌或私钥；Google工具由安装者自己的AI客户端管理。先复用已有连接，Search Console和GA4分别核验，任意Google连接存在不代表二者都可用。

缺连接时，Skill提供固定来源/版本的提供方候选与客户端配置引导；它不是内置的一键OAuth向导。用户可能需要自己的Cloud项目、API启用或网站资源权限，登录由本人完成。配置后还要实际读取本站数据才能报就绪。详见[Google接入](luxixi-workbench/references/google-mcp.md)。

### 工单如何执行

看板负责展示和复制，具体修复由用户自己的AI客户端执行。用户发送明确执行指令后，AI核对原库和工单、领取、在授权范围内处理并实际验证，最后回写。发布成功但回写失败时，先核对外部结果，不再次发布。未提供源码/部署权限时，只给建议并说明缺口。

### 日常启动、停止与数据

在已安装Skill目录中使用原数据根：

```text
python -X utf8 scripts/workbench.py service start --data-dir <原数据目录>
python -X utf8 scripts/workbench.py service status --data-dir <原数据目录>
python -X utf8 scripts/workbench.py service stop --data-dir <原数据目录>
```

服务只监听 `127.0.0.1`。默认数据位置使用系统用户数据目录，也可显式选择；数据库、日志和回执不作为静态网页提供。不要把数据目录提交到GitHub，不在不同电脑间共用同一执行数据库。

Windows固定入口、显式登录启动与保留数据卸载见[Windows说明](luxixi-workbench/references/windows.md)。卸载需本人明确要求，只删除核验过的当前安装副本，保留外置数据；未知文件/修改内容/链接先拒绝删除。电脑关机或休眠时不承诺服务/巡检运行。

### 当前限制

- Mac实机尚未验证；Mac登录启动和保留数据卸载适配尚未实现，不能使用Windows管理器替代。
- Windows整机重启、真实登录与休眠恢复仍未完整验收。
- Claude原生加载、领取/执行/回写全过程尚未实测；目录安装/离线封装不等于原生兼容。
- Codex原生工单闭环有历史0.4.0隔离证据，桌面巡检有历史0.6.0证据；当前0.6.1程序没有据此宣称全部原生组合已验。
- 自然定时触发、真实Google账号/站点数据仍无完整验收；触发未知不算自然运行。CLI与桌面/IDE/云端能力分别判断。
- 有限公开抽查不等于完整爬虫、Google收录或网站优化；流量变化不证明因果/收入。无事件埋点就不造历史按钮行为。
- 首版不支持Linux、跨电脑共享数据库、内置模型API网关或自动发布网站。

### 文档与许可证

[客户端入口](luxixi-workbench/references/clients.md) · [SEO巡检](luxixi-workbench/references/seo.md) · [工单协议](luxixi-workbench/references/tickets.md) · [统一周期](luxixi-workbench/references/cycle.md) · [版本说明](RELEASE.md)

项目代码使用[MIT](LICENSE)。第三方依赖和附带素材声明保持各自许可，见[NOTICE](NOTICE.md)、[第三方许可](THIRD_PARTY_NOTICES.md)及[固定版本清单](third_party/dependencies.json)。依赖实现、Python、AI客户端和Google MCP不随仓库捆绑，首次setup按固定版本从PyPI安装运行依赖。

Sources / Pre-Action Check：安装/初始化只写所选项目Skill、新运行环境与独立数据根并启动本机服务，不发布网站或创建SEO排期。命令依据包内脚本和[Python venv](https://docs.python.org/3.12/library/venv.html)；客户端/Google配置依据各引用文档。权限/依赖/端口/身份失败时保留数据并说明，不关闭安全设置或读取订阅凭据兜底。

## English

### What it is

Luxixi Local Workbench combines a **project-scoped Skill for Codex or Claude Code** with a local dashboard. Your AI chat guides installation, website onboarding and execution; the workbench displays website data, inspection reports, tickets and metadata from the Skill folders you approve.

Use your own AI client subscription and Google authorization. There is no built-in model, model billing gateway or required model API key. Each installation starts with a separate empty database. Developer websites, accounts, chats, databases and test schedules are not included.

### Features

| Feature | What it does |
| --- | --- |
| **SEO dashboard** | Per-site search performance and visitor data, separate 7-day/30-day/available-history windows, dates, gaps and trends. GSC and GA4 stay separate; missing data is not zero. |
| **Chat-led onboarding** | Collects your website, name, goals and market in the current chat. Reuses information already supplied and the same workbench for additional sites. Source code access is optional. |
| **Your own Google MCP** | Reuses or guides configuration of read-only Search Console and GA4 tools. Checks permissions, site identity and actual reads separately; you complete Google login yourself. |
| **Bounded read-only inspections** | Initial checks cover the homepage, robots and default sitemap. Later inspections sample at most six pages plus bounded robots/sitemap/apex-www checks, covering metadata, canonical/noindex, redirects and errors. Google index records are separate from live HTTP observations. |
| **Same-database tickets** | Copy a ticket to your AI, then claim, execute within scope, verify and report to the same database. Handles stale revisions, concurrent claims, repeated pastes and uncertain outcomes. Copying never starts execution. |
| **Cycles and effect reviews** | On explicit request, bind one supported client-native persistent task for all sites. Reviews link to the original optimization and evidenced deployment time, using 7/15/30-day windows. Insufficient data remains under observation; changes do not prove causality. |
| **Method research** | Reviews official guidance and open-source candidates in the same cycle, recording versions, sources, licenses and validation. Preserves the last complete result; never silently installs or adopts candidate code. |
| **Automation tab** | Shows tasks connected to this database, observed runs, next times, issues and receipts. Currently projects the unified SEO task; it does not discover every automation on your computer. |
| **Skill tab** | Reads metadata only from selected Skill folders, with categories, search, sources, versions and observed enabled state. Discovery is not execution permission. |
| **Local lifecycle** | Closing the browser leaves the page service running. Windows helpers provide a fixed entry, explicit login-startup management and uninstall that retains external data. |

### Quick start

Use an AI client with local file/command access, an existing Python 3.10+ installation and network access to download pinned dependencies. Installation tests used Windows 11 / Python 3.12.10. See the [compatibility matrix](COMPATIBILITY.md) for exact evidence. A web or cloud chat without a local connection cannot install the workbench or access your local database.

1. Download and extract this repository's ZIP, or clone it. Open your chosen workspace in Codex / Claude Code and ask the AI to read `luxixi-workbench/SKILL.md` and follow its installation guide.
2. Install only for the client you use. The installer writes project-scoped Skill folders; it does not change global Skill, MCP or Python settings.
3. Initialize a separate environment and data directory. Keep the returned actual URL and data directory for later commands.
4. Provide your website in chat, connect your own read-only Google tools and run the initial inspection. Then open the local workbench. Public-page checks can proceed without Google, with gaps shown explicitly.

Replace placeholders with your chosen absolute paths:

```text
# For Claude Code, use --client claude instead.
python -X utf8 <repository>/luxixi-workbench/scripts/install_skill.py --workspace <absolute-workspace> --client codex
```

From the **installed Skill directory**:

```text
python -X utf8 scripts/workbench.py setup --data-dir <absolute-separate-data-directory>
```

Use your existing `python3` command if that is its name on macOS; this is not a claim that macOS has passed acceptance. An optional `--port` selects the local port. Port conflicts fail without taking over another service.

Invoke `$luxixi-workbench` in Codex or `/luxixi-workbench` in Claude Code after installation. The client still needs to actually load the Skill and grant the required local-tool permissions.

### User journey

**Install Skill → provide your website in chat → authorize your own Google resources → run read-only checks → open the local workbench → optionally configure one unified cycle → copy a ticket to your AI → verify and write back.**

The three tabs are **SEO, Automation and Skill**. Your database starts empty. No approved scan folders means no discovered Skills; no schedule means no invented automation. `/demo/` is an explicitly synthetic, in-memory demonstration and does not populate your database.

The page polls local records every 30 seconds. It does not fetch Google data or run SEO every 30 seconds. Installing does not create a schedule. Scheduling requires an explicit request and an actually supported client-native mechanism. Paused/cancelled tasks stay paused; additional sites reuse the one unified task.

### Google connection and execution

The workbench does not collect Google passwords, tokens or private keys. Your AI client manages its own Google tools. Search Console and GA4 are verified separately; a generic Google connector alone does not establish either connection.

Missing connections may require MCP configuration, your own Cloud project, API enablement or site-resource permissions. This is not a built-in one-click OAuth wizard. Complete login yourself and verify an actual read for the selected site. See the [Google guide](luxixi-workbench/references/google-mcp.md).

The dashboard displays and copies tickets; your own AI performs the authorized work. It checks the existing database and ticket, claims only when execution is granted, makes the scoped change, verifies the actual result and writes back. If publishing succeeded but reporting failed, reconcile first instead of publishing again. Without source/deployment access, it reports advice and the missing capability.

### Start, stop and data

From the installed Skill directory, reuse the original data directory:

```text
python -X utf8 scripts/workbench.py service start --data-dir <original-data-directory>
python -X utf8 scripts/workbench.py service status --data-dir <original-data-directory>
python -X utf8 scripts/workbench.py service stop --data-dir <original-data-directory>
```

The service binds only to `127.0.0.1`. Data uses the operating system's user-data location or an explicit directory; databases, logs and receipts are not static web assets. Do not commit your data directory or share one execution database across computers.

See the [Windows guide](luxixi-workbench/references/windows.md) for the fixed entry, explicit login startup and data-retaining uninstall. Uninstall requires an explicit request, removes only the verified installation and preserves external data. Unknown/modified files and links cause refusal. Service/SEO operation is not promised while the computer is off or asleep.

### Known limits

- No macOS hardware acceptance yet; macOS login-startup and data-retaining uninstall adapters are not implemented. Do not use the Windows manager on macOS.
- Windows full reboot, real login and sleep/resume acceptance remains incomplete.
- The Claude native Skill/claim/execute/report journey has not been tested end to end. Directory installation and offline adapters are not native-client proof.
- Historical Codex native ticket evidence belongs to 0.4.0 and desktop inspection evidence to 0.6.0. These are not blanket native-compatibility claims for 0.6.1.
- Natural scheduled triggering and real Google account/site access lack full acceptance. Unknown triggers do not count as natural runs. CLI, desktop, IDE and cloud capabilities are evaluated separately.
- Bounded inspections are not a full crawler, proof of indexing or website optimization. Traffic changes do not prove causality or revenue. Missing event instrumentation cannot yield historical button behavior.
- The first release excludes Linux, cross-computer shared databases, a model API gateway and automatic website publishing.

### Documentation and license

Most bundled operational reference guides and the current dashboard are in Chinese; this README provides a bilingual overview and setup journey. See [client entry points](luxixi-workbench/references/clients.md), [inspections](luxixi-workbench/references/seo.md), [tickets](luxixi-workbench/references/tickets.md), [cycles](luxixi-workbench/references/cycle.md) and [release notes](RELEASE.md).

Project code is licensed under [MIT](LICENSE). Third-party dependencies and supplementary notices retain their own licenses; see [NOTICE](NOTICE.md), [third-party notices](THIRD_PARTY_NOTICES.md) and the [pinned inventory](third_party/dependencies.json). Dependency implementations, Python, AI clients and Google MCP servers are not bundled. Setup downloads the pinned runtime dependencies from PyPI.

Sources / Pre-action check: install/setup writes the selected project Skill, a separate environment and data root, then starts a loopback service. It does not publish a website or create an SEO schedule. Commands follow the bundled scripts and [Python venv](https://docs.python.org/3.12/library/venv.html). Client/Google configuration follows the linked guides. Missing permissions/dependencies, port conflicts or identity errors preserve data; do not disable security controls or extract subscription credentials as a fallback.
