# 有限回执协议 v1

回执是AI客户端本轮实际MCP调用结果的有限转交，不是网页或模型对Google访问成功的断言。只写本站需要的JSON结构；不要复制其他账号/项目、凭据、日志或原生聊天。CLI校验作用域与格式，不能独立认证客户端或Google签名，来源显示为客户端MCP回传；合成来源另标，不能当真实Google验收。

顶层字段：`service`为gsc或ga4；`server`是实际连接标识；`source`为client_mcp（正常）或synthetic_mcp（明确隔离测试）；`challenge`使用本站begin返回值；`observed_at`是本次实际读取的带时区ISO时间；`resource`是GSC属性或properties/N；`calls`最多8项，每项含operation/tool/arguments/result。总回执≤256KiB，不含密钥。失败用`error`枚举：not_connected/missing_tool/permission_denied/site_mismatch/binding_unknown/error；不能用error伪造read_ok/no_rows。

## GSC

`gsc.list_sites`保存当前资源那一项siteEntry和permissionLevel，排除其他站点。`gsc.query`保存原API响应rows（日期、clicks、impressions、position），不要把缺行补零。arguments规范为siteUrl、startDate、endDate、dimensions=[date]；可选type=web、dataState=final、startRow=0、rowLimit≤1000。日期按Search Console的PT日界，初检读取最近已经处理的窗口，不查询未来。

资源精确等于选定site时可无过滤；domain属性或更宽URL前缀必须使用下列唯一过滤组，把expression替换为`^`加完整规范site的正则转义。禁止额外query/country/device等子集冒充本站总量：

```json
{"dimensionFilterGroups":[{"groupType":"and","filters":[{"dimension":"page","operator":"includingRegex","expression":"^https://guide\\.example\\.com/"}]}]}
```

操作名是本协议归一化名称，不要求MCP工具同名。实际tool字段保留客户端调用名；若连接器只支持另一参数名，应将原查询无损映射到这里，不能捏造未发送的过滤。窗口≤91天，返回日期唯一/在窗口内，指标有限非负。

## GA4

`ga4.property`的arguments.property_id和result.name必须同一properties/N。`ga4.report`必须恰好一个date_ranges、dimensions=[hostName]，metrics按顺序为totalUsers、screenPageViews、sessions、newUsers；只接受明确本站作用域：

```json
{"property_id":"123","date_ranges":[{"start_date":"2026-10-01","end_date":"2026-10-07"}],"dimensions":["hostName"],"metrics":["totalUsers","screenPageViews","sessions","newUsers"],"dimension_filter":{"filter":{"field_name":"hostName","string_filter":{"match_type":"EXACT","value":"guide.example.com","case_sensitive":false}}}}
```

子路径site还使用and_group，第一项为上述hostname过滤，第二项为pagePath/BEGINS_WITH/规范site.path、case_sensitive=true。不能加来源、事件、页面等其他子集条件。result遵循GA Data API标准dimensionHeaders/metricHeaders/rows；人数来自唯一本站汇总行，不对每日/页面人数求和。

空行绑定可选`ga4.streams`，其arguments.property_id必须同一属性，result.dataStreams[].name也必须在该properties/N/dataStreams/下，webStreamData.defaultUri覆盖当前site。若工具没有此能力，空行保持binding_unknown。不会用不同属性的同站流证明当前属性。元数据只保留隐私阈值/明细合并布尔值及有无采样，未知自由文本不入库；未采集明细显示空缺，不伪造按钮/趋势。

## 记录和查看

将回执写入安装者获准的新临时文件后，调用`onboard --data-dir ... google-result --id ... --receipt ...`。程序只将有限派生结果与回执摘要写入本站记录，拒绝旧回执覆盖、未来时间、错challenge和合成/真实混用。超过24小时会派生陈旧状态，原时间保留。之后`check --id ...`记录公开初检并在聊天给实际工作台url和本站id。

正常check不允许回环/内网站点；合成会话明确禁止发公开网络请求，只能由隔离测试传输回写。测试时保持synthetic标记，不能用改source字段方式把测试结果放入真实库。

提供方格式：Google官方MCP 0.8.0原样返回proto snake_case，读取器明确兼容dimension_headers/metric_headers、dimension_values/metric_values、time_zone及有限已知元数据别名，同时兼容REST camelCase；同一字段出现冲突别名则拒绝。property_id支持数值、数字字符串或properties/N。operation与arguments是本协议的规范化范围证明，须按实际调用参数逐项映射，不能增加实际未用的过滤。result使用实际返回JSON，不由模型编造数值。
