# Hybrid Transfer

一个局域网文件传输原型项目，目标是在桌面端提供统一的发送/接收工作台，同时给移动设备，尤其是 Android 浏览器，提供可审批的轻量访问入口。

项目当前是 Python 实现的可运行原型，包含：

- 桌面端 `Tkinter` 图形界面
- 基于 UDP 广播的局域网设备发现
- 基于 TCP 的文件传输协议
- 基于本地 HTTP 服务的浏览器上传/下载入口
- 配对信任、任务状态持久化、断点续传、冲突处理
- 面向 Windows / Linux / macOS 的打包脚本

## 项目功能

### 1. 桌面端传输工作台

启动后会打开桌面窗口，提供以下能力：

- 浏览当前发现到的局域网设备
- 手动添加设备地址
- 选择目标设备并发送文件或文件夹
- 查看活跃任务与历史记录
- 保存共享目录、冲突策略、自动接受可信设备等配置
- 审批来自浏览器的访问请求

桌面入口在 [hybrid_transfer/__main__.py](/home/rocsun/project/hybrid_transfer/__main__.py) 和 [hybrid_transfer/desktop.py](/home/rocsun/project/hybrid_transfer/desktop.py)。

### 2. 局域网设备发现

每个实例会通过 UDP 广播自己的设备信息，并监听同一广播端口上的其他设备公告。公告中包含：

- `device_id`
- 设备名
- 传输端口
- Web 访问端口
- 平台类型

发现逻辑在 [hybrid_transfer/discovery.py](/home/rocsun/project/hybrid_transfer/discovery.py)。

### 3. 可信设备配对

设备之间并不是默认互信。桌面端可发起配对，生成 6 位验证码；验证码校验通过后，目标设备会被加入本地可信列表。只有可信对端才能通过 TCP 传输接口发起文件任务。

相关实现见 [hybrid_transfer/trust.py](/home/rocsun/project/hybrid_transfer/trust.py)。

### 4. TCP 文件传输

真正的文件内容传输走 TCP，自定义了一个很轻量的帧协议。支持：

- 任务报价/接受/拒绝
- 分块发送文件内容
- 每块 ACK 确认
- 任务完成确认
- 中断后重试和续传
- 冲突时覆盖、跳过、重命名

核心代码在 [hybrid_transfer/transfer.py](/home/rocsun/project/hybrid_transfer/transfer.py) 和 [hybrid_transfer/transfer_protocol.py](/home/rocsun/project/hybrid_transfer/transfer_protocol.py)。

### 5. 浏览器访客访问

桌面端还会启动一个本地 HTTP 服务，给浏览器提供访问入口，主要面向 Android 这类当前不做原生打包的设备。

浏览器首次访问时会生成一个待审批会话：

- 未审批前只能看到等待授权页面
- 桌面端审批后可上传文件到共享目录
- 审批后可下载共享目录中的文件
- 可查看最近任务

实现位于 [hybrid_transfer/web.py](/home/rocsun/project/hybrid_transfer/web.py)。

### 6. 任务与状态持久化

本地状态统一保存在 JSON 文件中，内容包括：

- 可信设备
- 任务列表
- 历史记录
- 断点续传索引
- 应用设置
- 当前选中的设备

实现见 [hybrid_transfer/persistence.py](/home/rocsun/project/hybrid_transfer/persistence.py)。

## 实现原理

### 整体架构

项目中心对象是 `CoreService`，它把几个子系统组装在一起：

- `JsonStateStore`：持久化状态
- `DiscoveryService` + `DiscoveryRegistry`：设备发现与缓存
- `TrustManager`：配对与可信校验
- `TaskManager`：任务状态流转
- `TcpTransferServer`：接收 TCP 传输
- `TransferCoordinator`：发起 TCP 传输
- `GuestAccessController` + `LocalWebGatewayServer`：浏览器访客访问

装配逻辑在 [hybrid_transfer/core.py](/home/rocsun/project/hybrid_transfer/core.py)。

### 文件传输流程

一次桌面到桌面的发送流程大致如下：

1. 发送端在 UI 中选择目标设备和文件。
2. `TransferCoordinator` 展开目录，计算文件大小和 SHA-256，创建任务。
3. 发送端通过 TCP 建连，先发送 `TASK_OFFER`，其中带上任务 ID 和文件清单。
4. 接收端 `TcpTransferServer` 检查发送方是否可信。
5. 接收端根据配置或人工审批结果返回 `TASK_ACCEPT` 或 `TASK_REJECT`。
6. 若接受，接收端还会对每个文件给出接收计划：
   - 是否跳过
   - 是否重命名
   - 当前已接收偏移量
7. 发送端从指定偏移继续，按块发送 `CHUNK`。
8. 接收端把内容写入 `.incoming/<task_id>/*.part` 临时文件，并返回 `CHUNK_ACK`。
9. 全部块完成后，发送端发送 `TASK_COMPLETE`。
10. 接收端把临时文件原子替换到最终共享目录，任务完成。

### 断点续传原理

断点续传依赖 `ResumeIndex`：

- 每个任务维护一个 `resume_index`
- 记录每个文件已接收字节数、临时文件路径、最终路径、完成状态
- 连接中断后，任务会被标记为 `retryable`
- 再次重试时，接收端在接受阶段返回每个文件的当前偏移量
- 发送端从该偏移继续传输，而不是从头重发

实现见 [hybrid_transfer/resume.py](/home/rocsun/project/hybrid_transfer/resume.py)。

### 冲突处理原理

当目标共享目录中已存在同名文件时，接收端根据策略处理：

- `overwrite`：覆盖原文件
- `skip`：跳过该文件
- `rename`：保存为 `name (copy).ext`

逻辑位于 [hybrid_transfer/tasks.py](/home/rocsun/project/hybrid_transfer/tasks.py) 和 [hybrid_transfer/transfer.py](/home/rocsun/project/hybrid_transfer/transfer.py)。

### 浏览器访问原理

浏览器访问走的是另一条更轻量的链路：

- 浏览器访问 `/`
- 服务端根据 `User-Agent` 和 cookie / token 判断是否是移动浏览器、是否已有访客令牌
- 若无有效授权，则创建待审批访客会话，并返回等待页面
- 桌面端审批后，浏览器可调用：
  - `POST /upload?name=...` 上传文件
  - `GET /download?name=...` 下载文件
- 下载和上传都会校验访客 token，并限制路径不能逃逸出共享目录

这套设计让 Android 设备即使没有原生客户端，也能通过浏览器参与传输。

## 代码结构

```text
hybrid_transfer/
  __main__.py            桌面程序入口
  core.py                核心服务装配
  desktop.py             Tkinter 桌面 UI
  desktop_state.py       UI 状态映射与控制器
  discovery.py           UDP 发现与设备注册
  trust.py               设备配对与信任
  tasks.py               任务状态与冲突策略
  transfer.py            TCP 发送端/接收端实现
  transfer_protocol.py   帧协议
  resume.py              断点续传索引
  persistence.py         JSON 状态持久化
  web.py                 浏览器访问网关
  release.py             发布信息与打包辅助

tests/
  test_hybrid_transfer.py
  test_transfer_runtime.py
  test_desktop_ui.py
  test_mobile_browser.py
  test_packaging_release.py
```

## 运行方式

### 环境要求

- Python 3.11+（项目代码使用了现代类型标注和标准库 HTTP / Tkinter 能力）
- 桌面端需要本机可用的 `tkinter`

### 启动项目

```bash
python3 -m hybrid_transfer
```

也可以指定状态文件位置：

```bash
python3 -m hybrid_transfer --state-path .hybrid_transfer/state.json
```

启动后会同时拉起：

- 桌面 UI
- TCP 文件接收服务
- 本地 Web 网关
- 局域网发现服务

默认端口基于 `9100`：

- 发现服务基准端口：`9100`
- Web 端口：`9101`
- TCP 传输端口：`9102`

## 测试

项目当前有比较完整的单元测试和运行时回归测试，覆盖：

- 状态存储
- 设备发现
- 可信配对
- 任务状态
- TCP 传输与续传
- 浏览器访问
- 桌面状态与交互
- 打包与发布输出

运行方式：

```bash
python3 -m unittest \
  tests/test_hybrid_transfer.py \
  tests/test_transfer_runtime.py \
  tests/test_desktop_ui.py \
  tests/test_mobile_browser.py \
  tests/test_packaging_release.py
```

## 打包发布

项目包含面向桌面平台的打包脚本：

- `scripts/build_linux.sh`
- `scripts/build_macos.sh`
- `scripts/build_windows.sh`
- `scripts/build_windows.bat`

打包依赖见 [requirements-packaging.txt](/home/rocsun/project/requirements-packaging.txt)：

```bash
python3 -m pip install -r requirements-packaging.txt
```

Android 当前不做原生客户端打包，而是通过浏览器入口访问。

## 当前边界

这是一个原型项目，重点在验证混合式局域网传输方案本身，已经具备清晰的主干能力，但仍有一些明显边界：

- 浏览器侧能力较轻，主要是共享目录上传/下载
- 安全模型目前以局域网信任和访客审批为主，还不是完整的生产级方案
- 发现机制使用 UDP 广播，更适合家庭/办公网段，不适合跨网段场景
- 目前没有 Android 原生客户端

如果把这个项目一句话概括，它的核心思想是：

“桌面端作为局域网文件交换中枢，桌面对桌面走可信 TCP 传输，移动端尤其 Android 走受控浏览器入口，从而在不同系统之间实现统一的局域网文件互传体验。”
