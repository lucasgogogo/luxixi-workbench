# 撸西西的本地工作台 · 聊天安装与接入

本机底座沿用已确认的SEO、自动化、Skill三Tab。首次启动为空；接入由安装者在Codex或Claude Code本机聊天中调用luxixi-workbench Skill完成。右上“接入说明”提供Skill包下载、聊天调用提示和当前接入状态，不要求先在网页填表。

Skill包位于skills/luxixi-workbench，下载版为downloads/luxixi-workbench.zip。包内scripts/install_skill.py只安装到用户指定工作区的原生项目Skill目录；scripts/workbench.py setup在Skill包内建立独立运行环境，输出实际数据根/本机地址。后续onboard命令登记网站、续办、只读扫描用户选定的Skill元数据目录、接收有限MCP回执和公开初检。没有注册/写入Google权限或模型API Key。

Google MCP来自安装者自己的AI客户端。Skill引导分别核验GSC属性范围/权限/日期报告和GA4属性/精确站点汇总，再将本次实际工具结果回传本机。同一站点幂等，缺工具/权限/站点绑定/无行/读取失败/陈旧分别显示；回执入口不代替客户端或Google认证，来源是客户端MCP回传。合成模式持续标注，不得当真实Google成功。

网页服务只监听127.0.0.1，首次默认端口8876，成功后保存选定端口。启动后独立运行，关掉网页不会停止服务。再次start复用同一数据目录的实例和入口；端口被其他程序占用时直接失败，不停止其他程序。默认不启用登录启动/自动重启，也不建立SEO时钟。

## 当前启动方式

开发环境是本目录独立.venv，依赖版本见requirements.lock；没有复用原工作台环境。首次安装优先使用Skill包的bootstrap，命令/权限与失败处理见Skill的references/clients.md。

Windows在本目录用workbench.ps1的start/status/stop动作；可传DataDir及Port。已安装Skill可按references/windows.md查看固定入口、显式登录启动与保留数据卸载，管理工具为scripts/manage_windows.py。Mac入口为`sh workbench.sh start`、`status`、`stop`，尚未做Mac实机验收；Windows直接调用登录入口不等于整机重启/真实登录触发已验收。

默认数据目录由platformdirs按安装者系统决定：Windows用户本地应用数据下的LuxixiWorkbench/main，Mac用户Library/Application Support/LuxixiWorkbench/main。也可显式指定独立数据目录；不允许接入无本应用身份标记的非空目录或不兼容数据库。停止服务保留数据库，不提供删除用户数据命令。

## 页面和记录

- `/`：本机记录库；当前为空。读库失败返回明确503，页面保留已读画面并标本轮未知，首次失败不当空库。
- `/demo/`：明确标注的合成演示，数据只在页面内存中，不写入本机库。
- `/api/automation`、`/api/seo`、`/api/skills`、`/api/onboarding`、`/api/tickets`：网页只读记录。网站登记/所选目录扫描/有限MCP回执仅通过本机typed CLI，不开放网页写接口；工单领取与回写通过ticket typed CLI完成，网页无写接口；程序不执行修复或发布。

数据库、服务控制信息和日志都在独立数据目录，不作为静态文件提供；静态服务只允许固定网页资产。控制接口只供本机CLI使用，不向网页开放停止按钮。status/stop请求禁代理和重定向，控制信息不放进网页或工单。

## 组件与范围

后端是本项目新写的Flask/Waitress/SQLite外壳，平台目录用platformdirs；版本/许可继承随包元数据并在私有Task报告核对。网页从用户已确认v0.2的逐项前端来源实现，保留两套侧栏、布局与流程。当前目录是私有开发候选，尚未完成最终许可证、发行清单、兼容矩阵或公开发布审查，不能整体上传。

操作依据/Pre-Action Check：上述入口只启动/读取/停止本产品新服务，无第三方业务平台操作；无Google、DNS、账号或SEO调度。缺依赖、端口占用、身份/库版本不符或进程异常时明确失败，保留数据，不接管其他服务。官方依据：[Flask+Waitress](https://flask.palletsprojects.com/en/stable/deploying/waitress/)、[Waitress参数](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html)、[平台目录](https://platformdirs.readthedocs.io/en/latest/api.html)、[SQLite连接/事务](https://docs.python.org/3.12/library/sqlite3.html)。


## 工单记录协议

用户把“复制执行提示词”发给自己的AI后，AI使用提示中的准确库ID、数据根、修订和内容摘要领取；复制本身不改状态。ticket CLI支持create/show/prompt/revise/claim/heartbeat、外部意图、report/recover/reconcile及有证据的安全retry。网站或任务必须已经接入，不自动生成真实业务工单。具体结构与恢复规则见skills/luxixi-workbench/references/tickets.md。

领取凭据、外部意图及不可变回执留在本数据根claims/intents/receipts；它们和artifacts不进入下载包。只读API不暴露领取密钥。回执需实际验证文件及摘要，工具检查绑定/完整性，不独立判定业务正确或已上线。外部动作已发意图后不能从本单再次发出，即使暂时查不到结果也需核对。数据库有独立ID及本机根绑定，复制或移动执行库不会自动作为另一套队列运行。

## Codex与Claude Code适配

本机聊天按Skill的references/codex.md或claude.md执行同一个ticket CLI。client detect只观察所选CLI版本、必要旗标和登录类别；prepare生成绑定工作区、库ID、修订和摘要的交接文件，不领取工单。最后回复和退出码都不能代替同库回执及实际文件验证。

run-isolated是可选的Windows合成验收入口，只允许明确标记的新工作区、同目录合成库和无外部动作单。它使用客户端自己的订阅登录，隔离个人设置/MCP输入，不使用模型API Key或SDK。输出有上限，子进程在执行前加入本次Job Object；失败、超时或清理未确认都先查库，不自动再做业务动作。Mac自动启动器尚未验收，普通网页/云会话没有本机连接时只作讨论和交接。

Claude Code未登录时可完成检测和准备，实际原生执行保持待验证；不能从路径存在、离线模拟或其他客户端结果推断成功。真实网站发布和Mac实机需另有证据；持久时钟不能从离线适配测试推定。

## SEO只读巡检

在自己的聊天中调用Skill，复用已登记网站和同一库，按references/seo.md运行prepare→客户端实际只读MCP→finish。prepare固定站点、库ID、资源、时区、日期与有限URL；没有Google时仍可先做公开抽查。引擎不持有Google凭据，不调用模型或建立定时任务。

GSC最终web搜索与GA4访客分别呈现。近7/30天和本次可用历史窗口按项目独立选择；GA4每个窗口独立取得去重人数，不加总每日/页面用户。空行、缺工具、权限、部分/阈值/截断、失败、旧记录和陈旧各自标注；无按钮或漏斗事件就不造行为。

公开抽查最多6个页面及robots/默认地图/apex-www，限制响应/跳转/时长，不执行JS、不带Cookie。robots只记录源指令，Google保存的索引/抓取记录另列；HTTP正常或地图列出不代表收录。检查报告先不可变落盘并绑定完整摘要，再写同库历史；同回执重复不重抓，投影失败可恢复已绑定报告。尚未落完整绑定的中断保留缺口，不能覆盖日志或伪造成功。

同日期的部分组失败保留原行并显示失败/原观测时间，不混不同日期；旧缓存按自己的时间变陈旧。建议可以形成同问题复用的调查单，复制不领取，未授权自动修改/发布。不强制每次优化或写文章。统一周期、原优化记录效果复查与方法研究见下节。


## 原生统一巡检、效果和方法

用户明确要求排期后，在自己的本机客户端按Skill的references/cycle.md操作。cycle CLI只准备/校验原生任务读回，动态读取同库启用站点，管理本轮巡检回写；没有内置定时器、OS计划任务或模型API。只绑定一项原生持久任务，新增网站下轮复用。缺原生能力保持未配置；暂停/取消不恢复，手动补采与实际原生定时、合成调度分开记录。原生接口不返回触发类型时可在授权内只读执行，但以unknown独立记录，不计自然运行。原生回执是客户端报告，不是平台签名认证，验收需另核实际运行。

效果复查挂在原已确认上线的工单修订/hash/attempt，使用明确deployed_at及前后7/15/30天GSC最终数据，排除上线当天。原回执缺上线时间、缺日、陈旧或样本不足继续观察；不拿确认时间代替发布时间。本站流量变化不证明本次改动因果，也不代表所改页面效果或收入。监测异常按站复用同单，只在该项新鲜证据恢复时结束未领取的监测单，执行中的单仍走原领取/回写协议。

方法基线0.6.0随包提供，版本/能力/指纹/来源及研究历史显示于原“SEO方法”页。研究随同一巡检到期运行，完整研究7天复核、失败1天重试并保留最近完整研究。新候选需固定版本、许可/权限审查和隔离验证；记录不等于自动采用，不下载执行未知代码。本包未集成额外爬虫、统计或候选源码。
