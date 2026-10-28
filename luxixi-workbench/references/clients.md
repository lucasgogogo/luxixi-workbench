# 客户端安装与能力

本Skill提供本机项目级安装，使用用户已登录的AI客户端，不建立模型API调用层。普通网页/云会话只有在明确获得安装者本机文件/命令连接后才可执行这里的步骤，不能把远端目录当本机。

## 从包安装

下载并解压`luxixi-workbench.zip`。在用户选择的工作区安装：

```text
python <解压后的Skill目录>/scripts/install_skill.py --workspace <工作区绝对路径> --client codex
python <解压后的Skill目录>/scripts/install_skill.py --workspace <工作区绝对路径> --client claude
```

只选择实际使用的一个入口；`--client both`用于明确选择两者。`--dry-run`先显示目标而不写入。安装器只复制此Skill白名单到指定工作区的`.agents/skills/luxixi-workbench`或`.claude/skills/luxixi-workbench`，不改全局Skill、AGENTS或MCP配置。相同包重复安装复用，不明/被修改的同名Skill拒绝覆盖。安装到代码仓库后，保持该工作区被客户端打开；必要时新会话/刷新Skill清单，再显式调用本Skill。

Codex在聊天中用`$luxixi-workbench`；Claude Code可显式调用`/luxixi-workbench`。路径符合官方规则只证明已放到发现位置，是否加载还须客户端实际确认，不能用CLI版本号替代。

## Bootstrap与后续命令

在已安装的Skill目录中，先执行`scripts/workbench.py setup`，可加用户选择的`--data-dir`、`--port`。它建立包内独立.venv，安装锁定运行依赖并启动loopback服务，输出实际data_dir/url。缺Python3.10+或网络/执行权限时，说明缺口并由用户按官方Python路径解决，不改其全局Python或原工作台。重复setup保持同一数据根；不要把测试目录选成真实库。

后续命令统一以`python -X utf8 scripts/workbench.py onboard --data-dir <setup返回目录>`为前缀：

| 动作 | 后接参数 |
| --- | --- |
| 检查所选客户端能力 | `doctor --client codex`或`claude` |
| 登记网站 | `begin --client codex --site <网址> --name <名称> --goal <目标>` |
| 补目标/用户时区/允许目录 | `configure --id <ID> --goal <目标> --timezone <IANA时区> --allow-skill-dir <已选择目录>` |
| 只读所选Skill元数据 | `scan --id <ID>` |
| 写有限Google读取回执 | `google-result --id <ID> --receipt <JSON文件>` |
| 公开初检 | `check --id <ID>` |
| 查看/取消/继续 | `status`、`cancel`、`resume`，均带`--id <ID>` |

源码目录不是扫描前提；允许目录只用于元数据扫描，不把授权扩成全盘/正文/凭据/聊天读取。客户端路径只通过选定命令的版本观察，不读取其登录材料。时区只是偏好记录，持久巡检仍未配置。

服务控制用`python -X utf8 scripts/workbench.py service start|status|stop --data-dir <同一目录>`。这只管理本工作台实例，不停止占用端口的其他程序；默认不启用登录启动或SEO调度。Windows固定入口、显式登录启动和保留数据卸载见[windows.md](windows.md)。凭据缺失不通过提取订阅令牌、Cookie或模型API Key兜底。

Sources / Pre-Action Check：目标是安装本包到选定工作区/运行本机服务，无第三方业务写入。已核[Codex Skill](https://learn.chatgpt.com/docs/build-skills)、[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)、[Claude Code Skill](https://code.claude.com/docs/en/skills)、[Claude Code MCP](https://code.claude.com/docs/en/mcp)。失败时保留同名Skill/原库，改用实际支持的本机客户端或解决执行缺口，不伪报已安装。

## 同库工单客户端

Codex先读[codex.md](codex.md)，Claude Code先读[claude.md](claude.md)，再按[tickets.md](tickets.md)领取和回写。当前聊天已具备本机工具时直接处理工单；不必启动第二个客户端。

可选的检测和交接命令以`python -X utf8 scripts/workbench.py client`为前缀：

| 动作 | 后接参数 |
| --- | --- |
| 检测所选原生客户端 | `detect --client codex`或`claude` |
| 准备交接，不领取 | `--data-dir <同库根> --db-id <准确库ID> prepare --id <工单ID> --client codex --workspace <所选绝对路径>` |
| 新合成工作区原生验证 | `--data-dir <同库根> --db-id <准确库ID> run-isolated --plan <prepare返回文件>` |

隔离自动启动器当前仅验证Windows，要求本机订阅可用；Claude未登录则返回未启动，原生兼容仍待验证。只可使用明确标记的新合成工作区和无外部动作工单，不把真实库改成测试标记。模型回复、JSON或exit0均需与同库证据一致；超时或失败先查已有结果，不能换run_id自动再做业务动作。
