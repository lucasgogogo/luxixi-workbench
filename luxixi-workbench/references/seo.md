# 已接入网站的SEO只读巡检

先确认本机data_dir、准确database_id、已登记的project_id及本站范围。不要用开发者或其他站点的资源；普通网页没有本机执行能力时只作交接。检查公开页面不授权修网站、DNS、账号、发布或恢复暂停任务。用户仅要求审阅时保持只读评估，不提前开始新巡检。

## 固定读取范围

命令前缀为`python -X utf8 scripts/workbench.py seo --data-dir <同一数据根> --db-id <准确库ID>`。

1. `prepare --id <本站ID>`生成只读计划；可带`--start YYYY-MM-DD --end YYYY-MM-DD`、最多4个`--url <本站公开URL>`。默认截至UTC三天前，历史起点优先保留本库已有范围；一次窗口最多480天。近7/30天与同长度前期分别列出，“所有时间”指本次可用历史窗口，不是建站以来全部流量。GSC为最终web搜索数据、太平洋时区；结束日须早于当地今天。
2. 已知并由安装者选定资源时，可加`--gsc-resource <准确GSC属性>`、`--ga4-resource properties/<ID> --ga4-timezone <实际属性时区>`。缺资源保持未连接，不能猜ID/时区。优先复用此前接入记录；资源变更先核本站范围。prepare只生成计划，没有读取Google/网站或创建定时。
3. 保存返回plan_file和inspection_id。计划参数改变需新prepare，不能编辑原文件或换库。用户取消/接入范围变化后旧计划不能继续写入。

## 用当前客户端读取

读取计划中的requests，按实际可用工具映射以下只读操作。只调用已有且用户授权的MCP/连接器，不安装陌生服务器、不提供Google密码/令牌或模型API Key。缺工具/权限用错误类别记录，不以工具存在替代读数。

| 标准操作 | 对应能力 |
| --- | --- |
| gsc.list_sites | 属性列表/权限 |
| gsc.query | Search Analytics查询（最终web、指定日期/维度/本站过滤） |
| gsc.inspect | Google保存的URL索引版本；不等于实时测试 |
| gsc.sitemaps | 所选属性的地图读取状态 |
| ga4.property / ga4.streams | 属性实际时区/本站绑定，必要的网页流配置 |
| ga4.report | 原生run_report，精确hostname及可选本站路径过滤 |

GA4每个范围的summary是独立窗口的去重人数；不能把每日、页面或来源人数相加当总访客。daily/sources/pages/events只能说明实际采集到的维度。没有按钮事件、漏斗或历史数据就明确未采集；不补造点击或转化。GSC页面/查询返回行存在过滤和上限，不能加总当全站总数；点击/曝光、Google保存抓取与收录、网站访问必须分开。

提供方参数/输出存在差异。arguments按计划的标准Google范围记录，用于本机校验；若工具原生参数名不同，在native_arguments保留实际非敏感参数，按所选提供方官方说明映射，不能把标准计划冒充原始工具实参。不能映射/权限不支持则记录missing_tool；本包不声明所有MCP兼容。蛇形/驼峰GA4结果均有限归一化，时区、hostName、列、日期/行数不符会拒绝。

## 写回同一库

`receipt-template --plan <plan_file>`给出空回执骨架，本身没有数据读取。把真实调用填入本数据根`imports/`下的JSON：顶层保留inspection_id/database_id/project_id/challenge/source/observed_at；calls每项包含计划请求id、operation、arguments、实际tool标识及result，或error（missing_tool/not_connected/permission_denied/error/cancelled）。没有调用就保留空数组，不伪造结果。正常source为client_mcp；文件不含凭据或私人正文，最大8MiB。

随后`finish --plan <plan_file> --receipt <本数据根imports内JSON>`。它进行最多6个页面、robots/默认地图及apex/www的有限GET抽查：不执行JS、不带Cookie，拒绝私网及越界跳转，单响应512KiB、总时长35秒。静态完整HTML与SSR都可；未读取正文时保留缺口，不要求特定框架。robots只记录读取/观察，不是完整Google规则解释器；地图列出或HTTP200均不是收录证明。

回执/报告先落不可变日志，完整报告摘要绑定本库，再投影。重复同一已记录回执只读原结果，不再抓取。投影失败但报告摘要已绑定时，重复相同finish恢复日志，不重抓；跨24小时恢复保留原观测时间并标陈旧。采集中/日志缺失或摘要未绑定时明确中断，不自动伪造/覆盖；先核已有结果，再另建只读计划。新窗口数据失败保留原日期；同日期的部分组失败保留旧行并标本次缺口，不能混用不同窗口。

`show --inspection <ID>`读取报告；有实际证据且值得调查时，才`propose --inspection <ID> --finding <报告中的key>`生成/复用同问题调查单。它不领取、不修复或发布，也不自动关闭已执行工单。不值得改时继续观察即可。检查与真实优化记录分开；效果复查和原生排期另有后续能力，不能在此建立第二项时钟。

## 合成测试

仅明确登记的synthetic站点可用synthetic_mcp回执，且finish必须带`--public-fixture <imports内JSON>`。fixture为`{"source":"synthetic_http","responses":{URL:{"status":200,"headers":{},"body_base64":"..."}}}`；它不向公共网络请求。真实站点拒绝此选项。合成Google/网页结果只算隔离适配验证，不算真实Google连接或业务改善。

Sources / Pre-Action Check：上述步骤读取所选网站/本机新记录库，Google仅经安装者自己客户端只读工具；无优化/发布/账号或定时写操作。已核[Search Analytics](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)、[URL Inspection](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect)、[GA4报表](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport)、[元数据](https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/ResponseMetaData)。失败保留缺口和旧数据日期，不静默填零、换站/权限或创建API调用层。
