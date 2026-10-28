# 撸西西的本地工作台：兼容性

核对日期：2026-10-28。当前公开预览版0.6.1。以下按系统、客户端界面和实际能力列出结果；模型品牌或订阅本身不代表兼容。

当前规范ZIP：203995字节、57个payload，SHA256 `9f770633820f2728cf0e0f29f3fac7aafe43a8041617fd7004d22bca11e7042a`。该SHA仅指原程序ZIP；本表和配套compatibility.json随当前公开仓库及完整分发包提供，不在原程序ZIP内。旧版本结果保留原版本，不自动成为0.6.1的原生验收成绩。

## 系统与本地服务

| 系统 / 精确测试环境 | 候选 | 已验证 | 尚缺 | 证据编号 |
| --- | --- | --- | --- | --- |
| Windows 11 Pro，10.0.26200，AMD64；Python 3.12.10；Ego Lite 0.6.1.11 | 0.6.1 | 新目录安装、三Tab、固定端口、退出测试浏览器后同实例存活、服务停止/崩溃恢复、故障拒绝、保留数据卸载和同包重装 | 整机重启、真实Windows登录、休眠恢复均待验；新目录/venv不等于全新Windows系统镜像 | E-WIN、E-UI、E-CLOSE、E-IDENTITY |
| macOS；系统版本、CPU、Python及浏览器版本未观察 | 0.6.1 | 没有Mac实机通过项 | 缺获准隔离Mac；干净安装、三Tab、保活、恢复、权限及卸载均未测；Mac登录启动/保留数据卸载适配尚未实现 | E-MAC |

Windows登录启动的已验范围为自有合成Startup目录中的Unicode快捷方式管理和实际调用，不能代替真实登录。Windows管理工具不能用于Mac。Mac包内手动shell包装只是入口代码；默认隔离客户端自动启动器明确拒绝非Windows。上述源码检查不构成Mac运行证据。

## 客户端分层

“目录安装”只证明文件位于发现目录。“原生已验”需要该客户端实际读取Skill、使用本机工具并由同库证据验证。离线封装测试不计原生成绩。版本写“未记录”时不推测安装者当前版本。

| 客户端 / 系统 | 版本与候选 | Skill层 | 本机执行、领取与回写层 | 原生持久排期 / 自然触发层 | 证据编号 |
| --- | --- | --- | --- | --- | --- |
| Codex CLI / Windows | CLI 0.164.0-alpha.11.1；历史0.4.0候选 | 原生实际读取已验 | 合成HTML一次领取→修复→实际验证→同库回写，以及新会话不重做已验 | CLI没有Scheduled管理界面；本包未由CLI验证持久排期 | E-CODEX-040、D-CODEX |
| Codex CLI / Windows | 当前0.6.1；原生客户端版本未重新观察 | 项目目录安装已验，当前包原生加载未重验 | 25项离线适配回归通过；当前包原生闭环未重验 | 未验；不沿用桌面结果 | E-WIN、E-OFFLINE |
| Codex桌面原生会话 / Windows | app版本未记录；历史0.6.0 | 已实际使用该版本工作流；未另立Skill发现测试 | 双合成站巡检实际同库完成并保留数据缺口；这不是工单修复闭环测试 | 历史唯一测试绑定有创建/读回/暂停证据，开发测试排期现已删除；触发类型未知1，自然触发0 | E-CYCLE |
| Codex桌面 / Windows | 当前0.6.1；app版本未观察 | 未单独原生验收 | 未单独原生验收 | 未验 | E-UNTESTED |
| Codex IDE扩展 / Windows或Mac | 版本未观察；0.6.1 | 未验 | 未验 | 未验；IDE无Scheduled管理界面 | E-UNTESTED、D-CODEX |
| Claude Code CLI / Windows | 历史观察2.1.97；当前0.6.1 | 项目目录安装已验，原生加载待验 | 交接/参数等离线验证已验；原生领取、执行、回写、复查待验 | 未验；不把会话loop等同本机持久排期 | E-CLAUDE、E-WIN、E-OFFLINE、D-CLAUDE |
| Claude Desktop / Cowork / Windows | 版本未观察；0.6.1 | 未分别验收 | 未分别验收 | 未验；不由Claude Code CLI目录安装推定 | E-UNTESTED、D-CLAUDE |
| Codex CLI及桌面 / Mac | 各客户端版本未观察；0.6.1 | 均未验 | 手工交接仅有文档；默认隔离自动启动器未放行Mac | 未验 | E-MAC |
| Claude Code及Desktop / Mac | 各客户端版本未观察；0.6.1 | 均未验 | 未验；缺Mac生命周期适配 | 未验 | E-MAC |
| Kimi Code CLI / Windows或Mac | 本地版本未观察；0.6.1 | 仅核官方Skill能力；本包未验 | 本包无Kimi专用安装/交接适配，未验 | 未验，不推断具备或不具备 | E-UNTESTED、E-CLIENT-SCOPE、D-KIMI |
| Kimi Code Desktop / Windows或Mac | 本地版本未观察；0.6.1 | 未验 | 官方介绍本地工具，不是本包实际闭环 | 未验 | E-UNTESTED、D-KIMI |
| DeepSeek相关客户端 | 具体客户端、版本和系统未选定；0.6.1 | 未验 | 没有本产品原生闭环证据或专用适配 | 未验 | E-UNTESTED、E-CLIENT-SCOPE、D-DEEPSEEK |
| 普通网页或云会话，未配置本机连接 | 具体界面/版本未选定；0.6.1 | 可讨论/交接说明；本包未验加载 | 当前连接条件不能读写安装者本机同库；云端副本不作为本机队列 | 云排期不直接证明本机任务可运行 | E-UNTESTED、D-CODEX、D-CLAUDE |

## 数据与支持边界

所有通过项来自隔离合成资源。真实Google GSC/GA4授权读取仍未验；“Google MCP工具可见”不代表本站数据已接通。用户应在自己的客户端授权本人网站；凭据不进入本包。没有数据、失败和未知不填零。

电脑关机、休眠或客户端不可用时，不承诺SEO运行。页面服务登录启动与SEO原生排期分别验收。本包不提供模型API Key/网关兜底，不因某模型能回答问题就宣称具有本地工具或定时能力。Linux与跨电脑共用数据库不在首版范围。

## 证据摘要与官方依据

这些编号映射已保存的隔离验收记录。测试正文与本机路径不随本表公开；它们也不是独立第三方认证。本轮只读核验已有证据，没有重新运行历史模型、排期或系统事件。

- E-WIN / E-UI / E-CLOSE / E-IDENTITY：0.6.1的34项Windows生命周期检查、12项实际浏览器事实、关闭测试窗口后同实例存活、独立35项交付身份核对。
- E-OFFLINE：0.6.1的25项离线适配检查，明确包含模拟transport，不计原生客户端通过。
- E-CODEX-040：0.4.0原生测试ZIP为`cc20110725b939f1657065543e2962d3ef3f3be705b0a7ba1ae9cc8d7bc75bb8`；该版最终ZIP为`f11b2a326efcb46b95f17224af990ced691af64f395537277db5592128db66cf`。二者仅非合成提示分支差异已审计，原生合成流程一致；不能提升为0.6.1原生成绩。
- E-CLAUDE：历史2.1.97检测与未登录门记录。原生验收依安装者决定保留，不要求现在登录。
- E-CYCLE：0.6.0原生双站巡检实际完成；桌面版本未记录、触发类型未知，测试任务已暂停。本表不会恢复它。
- E-MAC / E-CLIENT-SCOPE / E-UNTESTED：当前白名单与源码平台门、已声明的测试范围和本轮无Mac环境记录；未测不代表厂商永久不支持。
- D-CODEX：[Skills](https://learn.chatgpt.com/docs/build-skills)、[Scheduled tasks](https://learn.chatgpt.com/docs/automations)。官方能力与本产品实测分别判断。
- D-CLAUDE：[Skills](https://code.claude.com/docs/en/skills)、[排期比较](https://code.claude.com/docs/en/scheduled-tasks)。终端、Desktop、Cowork与云会话的文件来源和执行条件分别核验。
- D-KIMI：[CLI Skills](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html)、[CLI开始](https://www.kimi.com/code/docs/en/kimi-code-cli/guides/getting-started.html)、[Code Desktop](https://www.kimi.com/en/help/kimi-code/desktop-getting-started)。只有提供方能力资料，尚无本包测试。
- D-DEEPSEEK：[FAQ入口](https://api-docs.deepseek.com/faq/)的实际目标本次无可读正文，不作为任何本机支持声明依据。

当前发布说明：本矩阵保留原验收版本、日期和缺口。GitHub公开预览不补齐Mac、Claude、自然触发、真实Google或Windows OS事件门。开发测试排期已删除，不随本仓库分发。

Public preview: this matrix preserves original tested versions and gaps. Publication does not complete macOS, Claude-native, natural-trigger, real-Google or Windows OS-event acceptance. The development test schedule was removed and is not distributed.
