# 脉冲 Pulse · Ubuntu 资源监控

一个使用 **PySide6 + QFluentWidgets + pyqtgraph** 开发的原生 Linux 桌面工具。
石墨灰与暖橙色界面、圆角卡片、中文进程用途、深浅主题。数据直接来自本机，不依赖浏览器或云服务。

## 功能

- **资源总览**：CPU、内存、网络、磁盘容量与整机 I/O；1 / 5 / 15 分钟真实采样趋势，切换资源、网卡和 GPU。
- **GPU 监控**：NVIDIA NVML 计算利用率、显存、温度、功耗与风扇，支持多 GPU；AMD / Intel 尝试读取内核公开的 sysfs 指标。
- **进程洞察**：按 CPU、RSS、显存数值排序；进程名、中文用途、PID、命令搜索；查看启动命令、用户和状态。
- **中文描述**：常见应用与系统服务映射、桌面应用中文元数据；Python / Node 仅依据命令行明确线索补充用途。未知进程显示“用途待识别”。
- **端口查询**：本机 TCP LISTEN、UDP 绑定端点，支持 IPv4 / IPv6、协议与地址范围筛选；从端口跳到所属进程，也可查询进程的关联端口。
- **进程结束**：确认后发送 SIGTERM，执行前验证 PID 与创建时间，防止 PID 被复用后误操作；不自动强制结束。
- **CSV 导出**：导出当前筛选结果，含中文描述；UTF-8 BOM 便于表格软件读取。
- **桌面体验**：暂停 / 继续、设置持久化、深浅主题、可用时驻留系统托盘、应用菜单入口；无系统标题栏，窗口按钮随主题切换。

## 安装包（推荐）

从 [GitHub Releases](https://github.com/kallcurry/ubuntu-Resource-Monitoring/releases) 下载
`pulse-monitor_0.1.1_amd64.deb`，适用于 **Ubuntu 24.04 x86_64 / amd64**。
安装包自带 Python、Qt 和 UI 组件，不需要运行下面的源码环境安装步骤。

```bash
sudo apt install ./pulse-monitor_0.1.1_amd64.deb
```

安装后从应用菜单搜索“脉冲资源监控”，或运行 `pulse-monitor`。
卸载使用 `sudo apt remove pulse-monitor`。设置保存在用户目录，卸载不会主动删除设置。
同时提供解压即用的 `pulse-monitor-0.1.1-linux-x86_64.tar.gz` 和 `SHA256SUMS` 校验文件。
显卡驱动沿用系统版本；apt 可能需要联网补齐 Ubuntu 图形系统库。

## 从源码启动

需要 Ubuntu 桌面、Python 3.10+。已在 Ubuntu 24.04、Python 3.13、PySide6 6.9.2 上验证。

```bash
git clone https://github.com/kallcurry/ubuntu-Resource-Monitoring.git
cd ubuntu-Resource-Monitoring
./setup.sh
./run.sh
```

`setup.sh` 在仓库的 `.venv` 中安装依赖；若当前 Python 已有兼容的 PySide6，会直接复用，不修改系统 Python 包。首次安装需要联网。Ubuntu 缺少 venv 时，安装对应的 `python3-venv` 系统包后重试。

Qt 固定为已验证的 PySide6 6.9.2。精简 Ubuntu 环境如提示缺少 `libEGL.so.1` 或 XCB cursor 库，可补装 Qt 的系统运行依赖：

```bash
sudo apt-get install libegl1 libopengl0 libxcb-cursor0
```

普通 Ubuntu 桌面通常已有这些图形库，安装脚本不会自动修改系统包。更多依赖见 [Qt 官方 Linux 要求](https://doc.qt.io/qt-6/linux-requirements.html)。

也可以使用自己的虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./run.sh
```

添加应用菜单入口（可选）：

```bash
./install-desktop-entry.sh
```

脚本仅创建当前用户的 `~/.local/share/applications/pulse-monitor.desktop`，不需要 root。删除此文件即可移除入口。移动仓库后需要重新执行脚本。主窗口采用无边框设计，顶部空白区域可拖动，双击可最大化 / 还原；右上角保留最小化、最大化 / 还原和关闭按钮，窗口边缘可缩放。

### 常用操作

1. 点击资源卡片切换趋势图；右侧选择 GPU；磁盘卡片底部切换网卡。
2. 进程页点击 CPU / 内存 / 显存表头排序，可输入“浏览器”“微信”“训练”等中文查找用途。
3. 端口页输入端口号，选中条目后点击“查看所属进程”。
4. `/` 或 `Ctrl+F` 聚焦搜索；总览页会先切换到进程页。
5. 顶部空白区域拖动窗口，双击最大化 / 还原；右上角按钮控制窗口。
6. “偏好设置”中调整 1–5 秒采样间隔。托盘能力缺失时，关闭窗口直接退出。

## 指标口径与能力边界

- 进程 CPU 按**整机总算力 100%**归一化，因此与默认 `top` 的单核 100% 口径不同。
- 内存已用量为 `total - available`。进程内存为 RSS，含共享页，不能简单相加作为系统已用内存。
- GPU 计算利用率与显存占用分别统计。进程显存依赖 NVIDIA 驱动能力，同一 PID 在同一张卡的计算/图形列表中去重，在不同卡之间累加。
- AMD / Intel 支持程度取决于 sysfs；当前不支持它们的进程显存归属。未提供的指标显示 `—`，不会伪装成零。
- 首次采样与暂停后恢复会重置差分基线，显示“采样中”。新出现的进程需要下一次采样后才有 CPU 百分比。
- 磁盘容量默认读取根分区 `/`；I/O 是**整机设备汇总吞吐量**，并非仅根分区。
- 普通用户可能看不到部分连接或 PID；界面会说明权限限制，不自动提权。不使用 root 运行作为默认方案。
- 15 分钟历史仅保存在当前会话内存中，程序启动前的区间没有曲线。暂停期间保留最后快照，较长的采样间断在曲线上断开显示。
- 通用解释器的用途说明是辅助信息，不是安全判断。命令视图会遮盖常见明确的密码 / token 参数。

## 数据与隐私

采集、处理和设置均在本机完成；应用运行时没有遥测和远程上传逻辑。只有主动选择“导出 CSV”才写出进程数据。
设置保存在 `${XDG_CONFIG_HOME:-~/.config}/pulse-monitor/settings.json`。

## 开发与验证

```bash
.venv/bin/python -m pip install 'pytest>=8,<10'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
./run.sh --diagnose
```

测试包括真实采样、临时回环 TCP / UDP 端口识别、PID 身份校验、专用测试子进程的结束流程、GPU 显存去重、中文搜索、数值排序、刷新选择稳定性、跨页跳转、暂停、CSV、设置容错以及无边框窗口的主题、最小化、最大化和关闭到托盘。测试不会结束其他应用进程。

原生页面截图验证：

```bash
QT_QPA_PLATFORM=offscreen ./run.sh \
  --config-dir /tmp/pulse-test-config \
  --screenshot-dir runtime-screenshots \
  --quit-after 10
```

**截图包含真实主机和进程信息**；`runtime-screenshots/` 已加入忽略列表。自动化环境需允许读取 `/proc`、NVML 和回环 socket；严格沙箱里只能看到被隔离的进程或设备。

项目结构：

```text
pulse_monitor/
  __main__.py       启动、诊断与验证入口
  app.py            三个页面、操作、设置与托盘
  widgets.py        资源卡片、GPU 环形图与趋势图
  collectors.py     psutil / NVML / sysfs 采集与进程身份校验
  descriptions.py   中文用途映射与命令显示
  data.py           不可变数据快照与格式化
  table_models.py   表格模型、数值排序、过滤和委托绘制
  worker.py         后台采样线程
  theme.py          深浅色主题
tests/              采集、操作与 Qt 界面测试
docs/               设计评审稿与浏览器交互原型
```

## 后续方向

告警阈值、历史持久化、迷你悬浮窗，以及 AMD / Intel 更完整的指标适配。

## 构建安装包与发布

在 Ubuntu 24.04 x86_64、Python 3.12 的独立环境中：

```bash
python3.12 -m venv .venv-build
.venv-build/bin/python -m pip install -r requirements-build.txt
.venv-build/bin/python scripts/build_release.py
```

需要 `dpkg-deb`、`desktop-file-validate` 以及 Qt 运行库。输出在 `release/`：
`.deb` 安装包、便携版 `.tar.gz` 和 SHA-256 校验值。PyInstaller 将解释器和应用依赖一起打包，NVIDIA 驱动库从目标系统读取。

`.github/workflows/release.yml` 会在打包相关代码变更时自动构建、测试便携版和已安装应用，并验证卸载。
推送与项目版本一致的标签（例如 `v0.1.1`）时，全部验证通过后，才创建并发布带安装包附件的 GitHub Release。

## 许可证与依赖

本项目采用 [GPL-3.0](LICENSE)。第三方组件遵循各自许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。QFluentWidgets 上游另外提供商业授权方案。
