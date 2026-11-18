"""Conservative Chinese process descriptions; no inference of safety or intent."""

from functools import lru_cache
from pathlib import Path
import configparser
import re
import shlex

KNOWN = {
    "PulseMonitor": "脉冲 · 系统资源监控", "pulse-monitor": "脉冲 · 系统资源监控",
    "chrome": "谷歌浏览器", "chromium": "Chromium 浏览器", "firefox": "火狐浏览器",
    "msedge": "Edge 浏览器", "code": "VS Code 代码编辑器", "code-insiders": "VS Code 预览版",
    "codex": "Codex 开发助手", "chatgpt": "ChatGPT 桌面应用",
    "gnome-shell": "GNOME 桌面合成器", "gnome-terminal-server": "GNOME 终端",
    "gnome-terminal-": "GNOME 终端", "gnome-session-binary": "GNOME 桌面会话",
    "gnome-session-b": "GNOME 桌面会话", "gdm": "桌面登录管理器", "gdm3": "桌面登录管理器",
    "nautilus": "文件管理器", "Xorg": "X11 图形显示服务", "Xwayland": "X11 兼容显示服务",
    "kwin_wayland": "KDE Wayland 合成器", "plasmashell": "KDE 桌面外壳",
    "systemd": "系统与用户服务管理", "systemd-resolved": "本地 DNS 解析服务",
    "systemd-resolve": "本地 DNS 解析服务", "systemd-journald": "系统日志服务",
    "systemd-journal": "系统日志服务", "systemd-udevd": "硬件设备管理服务",
    "NetworkManager": "网络连接管理", "wpa_supplicant": "无线网络认证服务",
    "pipewire": "音视频流服务", "pipewire-pulse": "PulseAudio 兼容音频服务",
    "wireplumber": "音视频会话管理", "pulseaudio": "音频服务",
    "sshd": "SSH 远程登录服务", "ssh": "SSH 连接客户端", "cupsd": "打印服务",
    "avahi-daemon": "局域网设备发现服务", "redis-server": "Redis 缓存服务",
    "postgres": "PostgreSQL 数据库", "mysqld": "MySQL 数据库", "mariadbd": "MariaDB 数据库",
    "nginx": "Nginx Web 服务", "apache2": "Apache Web 服务",
    "dockerd": "Docker 容器服务", "containerd": "容器运行时", "docker-proxy": "容器端口代理",
    "nvidia-persistenced": "NVIDIA 驱动常驻服务", "nvidia-persiste": "NVIDIA 驱动常驻服务",
    "bash": "Bash 命令解释器", "zsh": "Zsh 命令解释器", "fish": "Fish 命令解释器",
    "sh": "Shell 命令解释器", "sudo": "权限切换工具", "dbus-daemon": "桌面消息总线",
    "dbus-broker": "桌面消息总线", "snapd": "Snap 软件包服务", "cron": "定时任务服务",
    "tracker-miner-fs-3": "文件搜索索引服务", "tracker-miner-f": "文件搜索索引服务",
    "rsyslogd": "系统日志转发服务", "unattended-upgr": "自动更新服务",
    "bluetoothd": "蓝牙设备服务", "upowerd": "电源状态服务", "polkitd": "系统授权服务",
    "ibus-daemon": "输入法框架", "fcitx5": "中文输入法框架", "at-spi-bus-launcher": "辅助功能服务",
    "ollama": "本地大模型服务", "uv": "Python 项目与依赖管理", "git": "Git 版本管理",
    "apt": "系统软件包管理", "apt-get": "系统软件包管理", "dpkg": "Deb 软件包管理",
    "gnome-software": "软件中心", "gnome-control-center": "系统设置",
    "wechat": "微信桌面客户端", "WeChat": "微信桌面客户端",
    "WeChatAppEx": "微信辅助进程", "WeChatApp": "微信桌面客户端",
    "QQ": "QQ 桌面客户端", "qq": "QQ 桌面客户端",
    "wemeet": "腾讯会议", "wemeetapp": "腾讯会议", "WemeetApp": "腾讯会议",
    "dingtalk": "钉钉桌面客户端", "feishu": "飞书桌面客户端",
    "slack": "Slack 团队沟通", "discord": "Discord 通讯客户端",
    "telegram-desktop": "Telegram 桌面客户端", "thunderbird": "邮件客户端",
    "QtWebEngineProcess": "嵌入式浏览器辅助进程", "QtWebEngineProc": "嵌入式浏览器辅助进程",
    "gvfsd": "虚拟文件系统服务", "gvfsd-smb": "SMB 网络共享访问",
    "gvfsd-fuse": "虚拟文件系统挂载", "gvfsd-metadata": "文件元数据服务",
}
KNOWN_CASEFOLD = {key.casefold(): value for key, value in KNOWN.items()}


@lru_cache(maxsize=1)
def desktop_names() -> dict[str, str]:
    """Read metadata only. Desktop Exec lines are never executed."""
    result: dict[str, str] = {}
    roots = [Path("/usr/share/applications"), Path("/usr/local/share/applications"),
             Path.home() / ".local/share/applications"]
    for root in roots:
        for file in root.glob("*.desktop"):
            try:
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.read(file, encoding="utf-8")
                entry = parser["Desktop Entry"]
                title = entry.get("Name[zh_CN]") or entry.get("Name[zh]")
                args = shlex.split(entry.get("Exec", ""))
                if title and args:
                    result[Path(args[0]).name] = title
            except (OSError, ValueError, configparser.Error, KeyError):
                continue
    return result


def describe(name: str, command: list[str] | tuple[str, ...] = ()) -> str:
    base = Path(name).name
    tokens = [str(v) for v in command]
    args = " ".join(tokens[1:]).lower()
    if re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", base):
        if "pulse_monitor" in args:
            return "脉冲 · 系统资源监控"
        if any(re.search(r"(?:^|[/\s])" + module + r"(?:\b|\.py)", args)
               for module in ("uvicorn", "gunicorn", "flask", "http.server")):
            return "Python Web / API 服务"
        if re.search(r"(?:^|[/\s])train(?:ing)?(?:[_.-][\w.-]+)?\.py(?:\s|$)", args):
            return "Python 训练脚本"
        if "jupyter" in args or "ipykernel" in args:
            return "Jupyter 笔记本 / 计算内核"
        script = next((Path(v).name for v in tokens[1:] if v.endswith(".py")), None)
        return f"Python 脚本 · {script}" if script else "Python 程序 · 具体用途待识别"
    if base in ("node", "nodejs"):
        if "vite" in args or "webpack-dev-server" in args:
            return "前端开发服务器"
        if "typescript" in args or "tsserver" in args:
            return "TypeScript 语言服务"
        if "vscode" in args or "/code/" in args:
            return "代码编辑器辅助进程"
        return "Node.js 程序 · 具体用途待识别"
    if base.startswith(("kworker/", "ksoftirqd/", "migration/", "rcu_")):
        return "Linux 内核工作线程"
    return KNOWN_CASEFOLD.get(base.casefold()) or desktop_names().get(base) or "用途待识别"


def display_command(arguments: list[str] | tuple[str, ...]) -> str:
    """Keep command context, mask common explicit credential flags."""
    result, redact_next = [], False
    sensitive = re.compile(r"(?:^|[-_])(?:password|passwd|token|api[-_]?key|secret)(?:$|=)", re.I)
    for raw in arguments:
        value = str(raw)
        if redact_next:
            result.append("••••")
            redact_next = False
        elif sensitive.search(value):
            if "=" in value:
                result.append(value.split("=", 1)[0] + "=••••")
            else:
                result.append(value)
                redact_next = True
        else:
            result.append(value)
    return shlex.join(result)
