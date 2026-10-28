# Claude Code 本机工单适配

仅适用于能执行本机文件/命令的Claude Code；普通Claude网页、Desktop或云任务不能直接借用CLI结论。先读本Skill与[tickets协议](tickets.md)，通过本项目`.claude/skills/luxixi-workbench`入口处理同一库，不复制数据根或提取其他客户端登录材料。

## 已打开聊天

使用`/luxixi-workbench`或由Skill识别带库ID/工单修订的明确执行请求。先show核对当前内容和既有结果；新领取明确放行后才在有限范围执行，验证后report。长执行使用heartbeat；中断/外部不明先核对，不换operation-id绕过锁。已完成则核对原证据后停止。所选工作区/记录程序不在权限范围时如实报告缺口，不谎称已回写。

Claude的工具权限、工单授权和Google OAuth是不同条件。不要使用跳过全部权限的开关，不代用户登录、获取API Key或修改账号权限。普通客户端未登录时，只完成可以离线完成的安装/命令准备，把原生执行标为待本人登录验证。

## 可选print合成验证

client prepare生成准确工作区与同库handoff，不领取；run-isolated只支持新标记合成工作区和无外部动作单。适配按本机help检测print、JSON输出/结构化格式、会话不持久化、项目设置和strict MCP等能力；旧版本缺旗标不静默省略防护。已有MCP与个人配置不作为隔离测试输入。

Windows若入口是npm的claude.cmd，适配器直接调用已安装node与公开cli.js，避免把提示或含空格路径交给batch shell拼接。用户现有Claude安装和全局配置保持原样，不捆绑客户端程序。

本机CLI的bare模式要求API认证，不用于本产品的订阅路径。登录通过Claude本人原生界面处理；适配器只提取是否有订阅的有限类别，不读取或显示email、token、密码或配置正文。print未登录或权限受阻时，不拿模拟进程输出冒充Claude成功。

JSON输出/structured_output必须匹配本次工单身份；工具结果/最终文字还要与同库回执和实际文件证据核对。exit0但无回执属于未验证；超时/非零退出不证明业务没执行，先查同库和既有证据，不自动重试。模拟transport只验证封装边界，不能列入原生Claude兼容成绩。

Sources / Pre-Action Check：已核[官方CLI](https://code.claude.com/docs/en/cli-reference)、[print模式](https://code.claude.com/docs/en/headless)、[Skills](https://code.claude.com/docs/en/skills)。操作本机新合成文件与记录库；订阅依赖本人登录。缺能力或未登录保留未验证，不自动切API计费或无权限模式。
