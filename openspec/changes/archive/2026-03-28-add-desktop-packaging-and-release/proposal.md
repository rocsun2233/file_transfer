## Why

当前程序已经具备真实 TCP 传输和完整首版桌面 UI，但仍缺少统一的桌面分发方案，导致它还不能以清晰、可重复的方式交付给 Windows、Linux、macOS 用户。现在需要补齐打包与发布流程，为三端提供统一产物结构、构建脚本、版本元数据和发布说明，并明确 Android 目前仅通过浏览器接入。

## What Changes

- 新增桌面三端统一的打包与发布能力。
- 新增基于 `PyInstaller` 的平台构建脚本与分发目录结构。
- 新增发布元数据、快速启动说明和版本清单。
- 新增产物级验证要求，覆盖程序启动、主窗口、默认共享目录和服务端口。
- 在发布说明中新增 Android 预留说明，明确当前不提供 Android 原生安装包。

## Capabilities

### New Capabilities
- `desktop-release-distribution`: 定义桌面端如何构建、整理、验证和说明 Windows、Linux、macOS 的分发产物。

### Modified Capabilities

无。

## Impact

- 影响仓库中的构建脚本、发布目录、版本元数据和说明文档。
- 影响如何在不同平台执行打包与验证流程。
- 不修改现有传输、发现和桌面交互行为，但会决定这些能力如何进入交付物。
