# Windows运行、恢复与保留数据卸载

使用安装时的外部Python及当前已安装Skill目录，准确复用setup返回的数据根。不要从将被卸载的运行环境启动卸载器。此入口只管理页面服务及其登录快捷方式，不管理客户端SEO巡检排期，不改Google或AI登录。

## 日常启动与恢复

```text
python -X utf8 scripts/workbench.py service start --data-dir <原数据根绝对路径>
python -X utf8 scripts/workbench.py service status --data-dir <原数据根绝对路径>
python -X utf8 scripts/workbench.py service stop --data-dir <原数据根绝对路径>
```

第一次默认8876，也可在setup明确选端口。成功启动后保存实际端口；后续不带port的start及setup复用同一入口。原端口被其他程序占用时会失败，不抢占或停掉该程序。只有用户明确选择新入口时才加`--port <新端口>`；已有收藏文件不同则保留并说明。

退出网页不停止服务；停止保留记录，重新start从同一库恢复。意外退出后先status，确认无匹配实例再start，不按猜测PID杀进程，不新建数据库兜底。电脑关机或休眠时不承诺可访问；恢复后核对实际服务和原排期，未执行的巡检不冒充已完成。

缺依赖或安装中断时，在原已安装副本执行setup修复本包独立环境，复用原数据根。被修改的包、未知环境、链接/目录身份或数据库版本冲突均先核对，不静默覆盖或降级。

## 固定入口和登录启动

管理命令前缀：`python -X utf8 scripts/manage_windows.py`，后接以下动作及同一`--data-dir <原数据根绝对路径>`：

| 动作 | 用途 |
| --- | --- |
| `status` | 查看实际页面服务和本安装绑定的登录快捷方式 |
| `entry` | 服务核验后，在数据根生成open-workbench.url；也可收藏返回的实际本机网址 |
| `enable-startup` | 仅在用户要求时，写当前用户Startup内一项本包专属快捷方式并读回 |
| `disable-startup` | 删除当前安装/同库绑定且内容未变的快捷方式，不停止当前服务或其他任务 |

启用后只在本人登录Windows时启动本机页面服务，不自动打开浏览器，不执行SEO。使用原安装的外部Python；Python或安装目录迁移后先核对/重新配置，不能假称旧快捷方式仍有效。配置成功、手动调用入口和真实登录触发是三种证据，分别报告。

`--synthetic-startup-dir`仅用于明确隔离验收，需要该目录有绑定同一数据根的合成标记；它不是实际Startup。正常安装者使用默认系统路径。`startup-run`是快捷方式内部入口，直接调用仍不能证明发生过系统登录。

## 保留数据卸载

用户明确要求卸载后，在要移除的已安装Skill目录，用外部Python运行：

```text
python -X utf8 scripts/manage_windows.py uninstall --data-dir <原数据根绝对路径>
```

先校验安装白名单/身份、数据根和快捷方式，停止匹配的本机服务，禁用本安装登录入口，再删除当前Skill程序及其独立运行环境。数据必须在安装目录外；数据库、网站/工单/报告与文件均保留，卸载回执写在数据根。没有删除数据选项；不要把“卸载”解释为删除项目资料或客户端原生SEO任务。

安装目录有用户文件、被修改的包/快捷方式或链接时，拒绝删除并指出位置，保留现场。独立环境也有安装文件归属清单；额外文件/目录、用户修改或缺清单时不删除环境，后续setup也不会把已有未知文件默认为程序文件。文件被占用或删除失败时显示未完成，先核对剩余文件，不反复自动清理。另一客户端安装副本不随当前卸载删除。

重装同一包后setup显式指定原数据根，会恢复原数据库身份、记录和端口；它不恢复已禁用的登录启动或暂停的SEO任务。客户端原生SEO排期若仍指向已移除副本，需用户在该客户端另行决定停用或改指向，卸载器不静默改它。

Sources / Pre-Action Check：只操作当前已核验安装、同库服务和自身Startup项。依据[Microsoft Startup](https://support.microsoft.com/en-us/windows/experience/startup-boot/configure-startup-applications-in-windows)、[Unicode ShellLink](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishelllinkw)、[Python venv](https://docs.python.org/3/library/venv.html)、[rmtree](https://docs.python.org/3/library/shutil.html#shutil.rmtree)。无第三方业务写入；权限/文件占用/依赖缺失失败时保留数据，不要求关闭安全软件、管理员提权或改原工作台。
