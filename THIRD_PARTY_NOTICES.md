# 第三方组件与许可

本仓库未捆绑第三方依赖实现或wheel，setup从PyPI安装下列固定版本。这里保留实际发行包附带许可原文，含原作者署名；项目MIT许可不覆盖它们。版本/许可文件摘要与依赖元数据见[机器清单](third_party/dependencies.json)。

| 组件 | 固定版本 | 许可范围 | 来源与全文 |
| --- | --- | --- | --- |
| Flask | 3.1.3 | BSD-3-Clause | [PyPI](https://pypi.org/project/Flask/3.1.3/) [许可1](third_party/licenses/Flask/flask-3.1.3.dist-info__licenses__LICENSE.txt) |
| Werkzeug | 3.1.9 | BSD-3-Clause；Silk图标附带CC-BY-2.5或3.0声明，图标实现/资产未随本仓库分发 | [PyPI](https://pypi.org/project/Werkzeug/3.1.9/) [许可1](third_party/licenses/Werkzeug/werkzeug-3.1.9.dist-info__licenses__LICENSE.txt)、[许可2](third_party/licenses/Werkzeug/werkzeug__debug__shared__ICON_LICENSE.md) |
| Jinja2 | 3.1.6 | BSD-3-Clause | [PyPI](https://pypi.org/project/Jinja2/3.1.6/) [许可1](third_party/licenses/Jinja2/jinja2-3.1.6.dist-info__licenses__LICENSE.txt) |
| MarkupSafe | 3.0.3 | BSD-3-Clause | [PyPI](https://pypi.org/project/MarkupSafe/3.0.3/) [许可1](third_party/licenses/MarkupSafe/markupsafe-3.0.3.dist-info__licenses__LICENSE.txt) |
| itsdangerous | 2.2.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/itsdangerous/2.2.0/) [许可1](third_party/licenses/itsdangerous/itsdangerous-2.2.0.dist-info__LICENSE.txt) |
| click | 8.5.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/click/8.5.0/) [许可1](third_party/licenses/click/click-8.5.0.dist-info__licenses__LICENSE.txt) |
| blinker | 1.9.0 | MIT | [PyPI](https://pypi.org/project/blinker/1.9.0/) [许可1](third_party/licenses/blinker/blinker-1.9.0.dist-info__LICENSE.txt) |
| waitress | 3.0.2 | ZPL 2.1 | [PyPI](https://pypi.org/project/waitress/3.0.2/) [许可1](third_party/licenses/waitress/waitress-3.0.2.dist-info__LICENSE.txt) |
| platformdirs | 4.11.5 | MIT | [PyPI](https://pypi.org/project/platformdirs/4.11.5/) [许可1](third_party/licenses/platformdirs/platformdirs-4.11.5.dist-info__licenses__LICENSE) |
| tzdata | 2026.4 | Apache-2.0（发行实现）；时区数据未捆绑，数据来源/权利按上游发行说明 | [PyPI](https://pypi.org/project/tzdata/2026.4/) [许可1](third_party/licenses/tzdata/tzdata-2026.4.dist-info__licenses__LICENSE)、[许可2](third_party/licenses/tzdata/tzdata-2026.4.dist-info__licenses__licenses__LICENSE_APACHE) |

Jinja2与itsdangerous的BSD-3-Clause、blinker的MIT由随包原文核对，不因METADATA的许可字段为空就填未知或默认MIT。ZPL、Apache及附带图标声明原样保留，不删版权人/原网址。

当前清单来自Windows/Python3.12.10的实际固定分发元数据；不表示Mac依赖解析已实测、没有漏洞或所有Python版本都支持。安装器另建venv与pip工具，Python/pip/SQLite实现不随此仓库分发；未来若捆绑它们须重新做相应分发许可审查。

Third-party dependencies are installed separately at the pinned versions. Their original notices and licenses are retained below and in third_party/licenses; the project MIT license does not relicense them. Dependency implementations and Python are not bundled.
