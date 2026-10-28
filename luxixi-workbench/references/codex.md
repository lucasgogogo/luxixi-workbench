# Codex 本机工单适配

用于已打开本机项目的Codex聊天或CLI。桌面、CLI、云会话分开判断；能讨论工单不代表同库可达。先读取本Skill及[tickets协议](tickets.md)，使用工单给定的准确库/修订/摘要/本地工具，不重走安装。

## 当前聊天执行

用户明确发来的执行指令覆盖原工单有限范围；先show，再用当前Codex会话actor与稳定operation-id领取。只有can_execute=true可动手；若已完成，核对既有文件/证据后停止，不再claim或report。执行范围、验证、先记外部意图与回执恢复完全沿用共同协议。不要用模型回复、thread完成或退出码替代同库last_result。

Windows运行Python用参数数组与UTF-8，保留中文/空格路径，避免字符串拼接shell。工单给出的argv_prefix及cwd是明确允许的本包程序；网站源文件/证据仍只限工单范围。需要将结果JSON写到文件时用实际换行与UTF-8，不把PowerShell转义或示例当真实结果。

## 可选新CLI合成验证

本包client命令提供detect与prepare；prepare仅生成本机交接计划，不领取。`run-isolated`只接受标记的新合成工作区、其内部的同库和无外部动作工单，不用于生产工单或自动发布。它启动新的`codex exec`，保留workspace-write与当前Windows MXC边界，不加载个人config/rules/项目指令正文，不恢复原会话；没有关闭sandbox或自动批准高权限动作的兜底。

订阅登录由Codex自身管理，适配器只看登录状态类别，不读取/复制认证材料。新进程移除API/provider环境项，仍须重新确认订阅可用；没有订阅或能力旗标不符就停在实际缺口，不使用API Key。模型使用该原生运行的默认选择，本包不设模型、网关或计费。

输出日志与final保留在本次新数据根client_runs；final需匹配库、工单、修订和摘要，但它只是客户端陈述。适配器还核同库实际完成回执、文件证据及本次actor/operation归因。exit0没回执不能报完成；超时/非零而同库已完成时保留业务完成并明确客户端异常，绝不重做。超时只停止本次自有进程树，不按名字结束其他Codex。

隔离前提不是完整读取隔离证明：workspace-write主要约束可写范围。实际测试应审计新运行工具记录，确认只读所给Skill/记录程序/合成资源，不把开关存在写成所有路径均受OS拒绝。新运行不能修改或恢复旧聊天、Google连接、原生任务或现有工作台。

Sources / Pre-Action Check：已核[原生exec](https://learn.chatgpt.com/docs/developer-commands)、[非交互执行](https://learn.chatgpt.com/docs/non-interactive-mode)、[权限](https://learn.chatgpt.com/docs/agent-approvals-security)、[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox)，并以本机--help为参数门槛。本机程序和订阅服务仅接收本次合成提示；缺原生能力保持未验证，不降级成无隔离模式。
