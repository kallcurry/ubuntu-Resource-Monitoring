脉冲 Pulse 首个原生安装包，面向 **Ubuntu 24.04 x86_64 / amd64**。

### 下载与安装

- **推荐：`pulse-monitor_0.1.0_amd64.deb`**，包含 Python、Qt 和 UI 组件，安装后从应用菜单搜索“脉冲资源监控”。
- `pulse-monitor-0.1.0-linux-x86_64.tar.gz`：便携版，解压后运行 `PulseMonitor/PulseMonitor`。
- `SHA256SUMS`：安装包校验值。

在下载目录执行：

```bash
sudo apt install ./pulse-monitor_0.1.0_amd64.deb
```

卸载：`sudo apt remove pulse-monitor`。不需要自行安装 Python 或创建虚拟环境。
安装器仅可能通过 apt 补齐 Ubuntu 图形系统库；显卡驱动沿用系统已安装版本。

### 功能

CPU / 内存 / GPU / 显存 / 网络 / 磁盘监控，实时趋势；中文进程说明、搜索与资源排序；端口到进程反查；CSV 导出；深浅主题；确认后结束进程。

NVIDIA GPU 使用 NVML；AMD / Intel 当前只显示系统可读的 sysfs 指标。部分进程和端口信息受当前用户权限限制。

发布前自动验证：原生测试、便携版诊断与 GUI 启动、`.deb` 安装、X11 启动与卸载。
