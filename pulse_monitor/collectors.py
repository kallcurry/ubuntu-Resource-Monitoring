"""Linux resource sampling, intentionally independent of Qt."""

from pathlib import Path
import os
import socket
import time

import psutil

from .data import GPUInfo, PortInfo, ProcessInfo, Snapshot
from .descriptions import describe, display_command
from .telemetry import Telemetry


def counter_rate(current: int, previous: int, elapsed: float) -> float | None:
    if elapsed <= 0 or current < previous:
        return None
    return (current - previous) / elapsed


class NvidiaProvider:
    def __init__(self):
        self.api = None
        self.note = ""
        try:
            import pynvml
            pynvml.nvmlInit()
            self.api = pynvml
        except Exception as error:
            reason = type(error).__name__
            if "LibraryNotFound" in reason:
                self.note = "未找到 NVIDIA 驱动接口"
            elif "DriverNotLoaded" in reason:
                self.note = "NVIDIA 驱动未加载，或当前环境无法访问显卡"
            elif "NoPermission" in reason:
                self.note = "当前用户没有读取 NVIDIA 指标的权限"
            elif isinstance(error, ImportError):
                self.note = "未安装 NVIDIA 采集组件"
            else:
                self.note = f"NVIDIA 指标不可用：{reason}"

    def collect(self) -> tuple[list[GPUInfo], dict[int, int], bool]:
        if not self.api:
            return [], {}, False
        api = self.api
        rows, memory, supported = [], {}, True
        try:
            count = api.nvmlDeviceGetCount()
            for index in range(count):
                handle = api.nvmlDeviceGetHandleByIndex(index)

                def query(function, *args):
                    try:
                        return function(handle, *args)
                    except api.NVMLError:
                        return None

                name = query(api.nvmlDeviceGetName) or f"NVIDIA GPU {index}"
                if isinstance(name, bytes):
                    name = name.decode(errors="replace")
                util = query(api.nvmlDeviceGetUtilizationRates)
                mem = query(api.nvmlDeviceGetMemoryInfo)
                temperature = query(api.nvmlDeviceGetTemperature, api.NVML_TEMPERATURE_GPU)
                power = query(api.nvmlDeviceGetPowerUsage)
                fan = query(api.nvmlDeviceGetFanSpeed)
                rows.append(GPUInfo(f"nvidia:{index}", str(name),
                                    float(util.gpu) if util else None,
                                    mem.used if mem else None, mem.total if mem else None,
                                    temperature, power / 1000 if power is not None else None, fan,
                                    "部分指标取决于显卡和驱动支持"))
                # Compute and graphics lists can contain the same PID: max per device,
                # then sum across different devices. Never count a PID twice on one GPU.
                device_memory: dict[int, int] = {}
                device_supported = False
                for function in (api.nvmlDeviceGetComputeRunningProcesses,
                                 api.nvmlDeviceGetGraphicsRunningProcesses):
                    records = query(function)
                    if records is None:
                        supported = False
                        continue
                    device_supported = True
                    for record in records:
                        value = record.usedGpuMemory
                        if value is not None and 0 <= value < (1 << 63):
                            device_memory[record.pid] = max(device_memory.get(record.pid, 0), value)
                supported = supported and device_supported
                for pid, value in device_memory.items():
                    memory[pid] = memory.get(pid, 0) + value
            return rows, memory, supported and count > 0
        except api.NVMLError as error:
            self.note = f"NVIDIA 采集失败：{type(error).__name__}"
            return rows, memory, False

    def close(self):
        if self.api:
            try:
                self.api.nvmlShutdown()
            except self.api.NVMLError:
                pass


def sysfs_gpus() -> list[GPUInfo]:
    rows = []

    def read_number(path):
        try:
            return int(path.read_text().strip())
        except (OSError, ValueError):
            return None

    for card in sorted(Path("/sys/class/drm").glob("card[0-9]*")):
        if "-" in card.name:
            continue
        device = card / "device"
        try:
            vendor = (device / "vendor").read_text().strip()
            if vendor not in ("0x1002", "0x8086"):
                continue
            brand = "AMD" if vendor == "0x1002" else "Intel"
            util = read_number(device / "gpu_busy_percent")
            used = read_number(device / "mem_info_vram_used")
            total = read_number(device / "mem_info_vram_total")
            rows.append(GPUInfo(str(device.resolve()), f"{brand} GPU · {card.name}",
                                util, used, total,
                                note="sysfs 指标；未提供的项目显示 —，暂不支持进程显存"))
        except OSError:
            continue
    return rows


class Collector:
    def __init__(self):
        self.cores = psutil.cpu_count() or 1
        self.gpu = NvidiaProvider()
        self.telemetry = Telemetry()
        self.previous_time: float | None = None
        self.previous_processes: dict[tuple[int, float], float] = {}
        self.previous_process_io = {}
        self.previous_network = {}
        self.previous_disk = None
        self.processes: dict[int, ProcessInfo] = {}
        self.ready = False

    def reset(self):
        self.previous_time = None
        self.previous_processes.clear()
        self.previous_process_io.clear()
        self.telemetry.reset()
        self.previous_network.clear()
        self.previous_disk = None
        self.ready = False

    @staticmethod
    def default_interface(interfaces: dict) -> str:
        try:
            for line in Path("/proc/net/route").read_text().splitlines()[1:]:
                fields = line.split()
                if fields[1] == "00000000" and int(fields[3], 16) & 2:
                    if fields[0] in interfaces:
                        return fields[0]
        except (OSError, ValueError, IndexError):
            pass
        return next((name for name in interfaces if name != "lo"), next(iter(interfaces), "无网卡"))

    @staticmethod
    def cpu_temperature() -> float | None:
        try:
            sensors = psutil.sensors_temperatures()
            for key in ("coretemp", "k10temp", "cpu_thermal", "zenpower"):
                values = [s.current for s in sensors.get(key, []) if s.current is not None]
                if values:
                    return max(values)
        except (AttributeError, OSError):
            pass
        return None

    def collect(self, network: str = "") -> Snapshot:
        started = time.monotonic()
        elapsed = started - self.previous_time if self.previous_time is not None else 0
        raw_cpu = psutil.cpu_percent(interval=None)
        cpu = raw_cpu if self.ready else None
        self.ready = True
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        try:
            frequency = psutil.cpu_freq()
        except (OSError, NotImplementedError):
            frequency = None
        interfaces = psutil.net_io_counters(pernic=True)
        name = network if network in interfaces else self.default_interface(interfaces)
        download = upload = None
        current = interfaces.get(name)
        previous = self.previous_network.get(name)
        if current and previous and elapsed:
            download = counter_rate(current.bytes_recv, previous.bytes_recv, elapsed)
            upload = counter_rate(current.bytes_sent, previous.bytes_sent, elapsed)
        disk = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()
        disk_read = disk_write = None
        if disk_io and self.previous_disk and elapsed:
            disk_read = counter_rate(disk_io.read_bytes, self.previous_disk.read_bytes, elapsed)
            disk_write = counter_rate(disk_io.write_bytes, self.previous_disk.write_bytes, elapsed)
        gpus, vram, vram_supported = self.gpu.collect()
        other_gpus = sysfs_gpus()
        gpus.extend(other_gpus)
        # When another vendor is present we cannot attribute its per-process memory.
        vram_supported = vram_supported and not other_gpus
        processes = []
        totals = {}
        process_io = {}
        attrs = ["pid", "name", "username", "cmdline", "memory_info", "create_time",
                 "cpu_times", "status", "uids", "num_threads", "ppid", "io_counters"]
        for proc in psutil.process_iter(attrs, ad_value=None):
            try:
                if not proc.is_running():
                    continue
                info = proc.info
                pid = info["pid"]
                created = info.get("create_time")
                key = (pid, created)
                times = info.get("cpu_times")
                process_cpu = None
                if times is not None and created is not None:
                    total = times.user + times.system
                    totals[key] = total
                    old = self.previous_processes.get(key)
                    if old is not None and elapsed > 0:
                        process_cpu = min(100.0, max(0.0, (total-old) / elapsed / self.cores * 100))
                arguments = info.get("cmdline") or []
                proc_name = info.get("name") or "名称不可读"
                rss = info.get("memory_info")
                uid = info.get("uids")
                io = info.get("io_counters")
                old_io = self.previous_process_io.get(key)
                read = write = None
                if io is not None and created is not None:
                    process_io[key] = io
                    if old_io is not None and elapsed > 0:
                        read = counter_rate(io.read_bytes, old_io.read_bytes, elapsed)
                        write = counter_rate(io.write_bytes, old_io.write_bytes, elapsed)
                processes.append(ProcessInfo(pid, created, proc_name, describe(proc_name, arguments),
                                             info.get("username") or "权限不足",
                                             uid.real if uid else None,
                                             display_command(arguments) if arguments else "命令不可读或内核线程",
                                             info.get("status") or "不可读", process_cpu,
                                             rss.rss if rss else None,
                                             vram.get(pid, 0) if vram_supported else vram.get(pid),
                                             cpu_available=times is not None and created is not None,
                                             threads=info.get("num_threads"), parent_pid=info.get("ppid"),
                                             read_rate=read, write_rate=write))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        self.processes = {p.pid: p for p in processes}
        details = self.telemetry.collect(memory, interfaces, self.previous_network, elapsed, disk)
        self.previous_time = started
        self.previous_processes = totals
        self.previous_process_io = process_io
        self.previous_network = interfaces
        self.previous_disk = disk_io
        return Snapshot(started, time.time(), cpu, self.cores,
                        frequency.current if frequency else None, self.cpu_temperature(),
                        memory.total, memory.available, swap.used, swap.total, name,
                        tuple(interfaces), download, upload, disk.used, disk.total,
                        disk_read, disk_write, tuple(gpus), tuple(processes),
                        max(0, time.time()-psutil.boot_time()), time.monotonic()-started,
                        self.gpu.note if not gpus else "", **details)

    def ports(self) -> tuple[tuple[PortInfo, ...], str]:
        rows = {}
        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError):
            return (), "权限不足：无法读取连接列表"
        except OSError as error:
            return (), f"端口采集失败：{error.strerror or type(error).__name__}"
        for connection in connections:
            if not connection.laddr:
                continue
            udp = connection.type == socket.SOCK_DGRAM
            if not udp and connection.status != psutil.CONN_LISTEN:
                continue
            pid = connection.pid
            proc = self.processes.get(pid)
            row = PortInfo("UDP" if udp else "TCP", connection.laddr.ip, connection.laddr.port,
                           pid, proc.name if proc else "进程信息受限",
                           proc.description if proc else "权限不足或进程已退出",
                           proc.created if proc else None)
            rows[row.key] = row
        note = "普通用户视图 · 部分连接或 PID 可能因权限不可见" if os.geteuid() else "系统连接视图"
        return tuple(sorted(rows.values(), key=lambda p: (p.port, p.protocol, p.address, p.pid or 0))), note

    def close(self):
        self.gpu.close()


def terminate_process(pid: int, created: float | None):
    """Caller must have shown confirmation. Validate identity before SIGTERM."""
    if pid <= 1 or pid == os.getpid():
        raise ValueError("不能结束系统初始化进程或监控程序自身")
    if created is None:
        raise ValueError("无法验证进程身份，请刷新后重试")
    proc = psutil.Process(pid)
    if abs(proc.create_time() - created) > 0.001:
        raise ValueError("PID 已被其他进程复用，操作已取消")
    proc.terminate()
