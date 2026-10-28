# 0.6.1 Preview / 预览版

Date / 日期：2026-10-28  
Repository / 仓库：https://github.com/lucasgogogo/luxixi-workbench  
Project license / 项目许可：[MIT](LICENSE)

This is an early public preview. Publication does not certify all operating systems, AI clients, real Google connections or naturally triggered schedules. Exact tested versions and unverified combinations are listed in [COMPATIBILITY.md](COMPATIBILITY.md).

这是公开预览版。公开源代码不代表Mac、Claude、自然定时或真实Google等完整验收已通过；准确版本与缺口见兼容矩阵。

## Program baseline / 程序基线

Version 0.6.1 contains 57 payloads plus `bundle-manifest.json`, 58 entries in total. Every program entry is byte-identical to the previously installation-tested baseline ZIP, SHA256 `9f770633820f2728cf0e0f29f3fac7aafe43a8041617fd7004d22bca11e7042a` (203995 bytes). The method baseline remains 0.6.0. No runtime behavior, UI layout or CSS changed for publication.

本次发布只更新外层中英文README、项目许可、NOTICE、版本/兼容说明及分发清单，增加`.gitattributes`防止Git克隆时改写payload换行。原程序逻辑和样式保持，不以文档变更伪称产品新增兼容能力。

`release-manifest.json` lists every repository distribution file except itself, with byte counts and SHA256. The complete distribution archive has its own SHA256 and must not be confused with the original program ZIP. Git control files, development reports, virtual environments, user data and test artifacts are excluded from the distribution archive. A fresh allowlisted Git history is used instead of copying old private history.

## Known gaps / 保留缺口

- macOS hardware acceptance and its login-startup/data-retaining uninstall adapters are incomplete.
- Windows actual OS reboot, real login and sleep/resume acceptance remains open.
- Claude native end-to-end execution, natural scheduling provenance and real Google access remain unverified.
- Historical Codex native results keep their original tested versions; the current program is not declared universally compatible.
- 浏览器仅刷新本地记录；电脑关闭/休眠或客户端不可用时不承诺运行，流量变化不作因果或收入保证。

The private development test schedule was removed and is not part of this repository or an installer-created task. Installation never creates an SEO schedule automatically. / 私有开发测试排期已删除，不随仓库或安装程序分发；安装不自动创建SEO排期。
