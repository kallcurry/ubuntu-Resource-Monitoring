"""Immutable snapshots shared between the collection thread and the UI."""

from dataclasses import dataclass, field
import ipaddress


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    created: float | None
    name: str
    description: str
    user: str
    uid: int | None
    command: str
    status: str
    cpu: float | None
    rss: int | None
    vram: int | None
    cpu_available: bool = True
    threads: int | None = None
    parent_pid: int | None = None
    read_rate: float | None = None
    write_rate: float | None = None

    @property
    def key(self) -> tuple[int, float | None]:
        return self.pid, self.created

    @property
    def io_rate(self) -> float | None:
        return self.read_rate + self.write_rate if self.read_rate is not None and self.write_rate is not None else None


@dataclass(frozen=True)
class HardwareInfo:
    cpu_model: str = "型号不可读"
    physical_cores: int | None = None
    distribution: str = "Linux"
    kernel: str = "—"
    architecture: str = "—"


@dataclass(frozen=True)
class NetworkInfo:
    name: str
    is_up: bool | None = None
    speed: int | None = None
    mtu: int | None = None
    ipv4: tuple[str, ...] = ()
    ipv6: tuple[str, ...] = ()
    mac: str = "—"
    download: float | None = None
    upload: float | None = None
    received: int = 0
    sent: int = 0
    packets_received: int = 0
    packets_sent: int = 0
    errors: int = 0
    dropped: int = 0


@dataclass(frozen=True)
class DiskInfo:
    name: str
    read_rate: float | None = None
    write_rate: float | None = None
    read_iops: float | None = None
    write_iops: float | None = None
    busy: float | None = None


@dataclass(frozen=True)
class PartitionInfo:
    mountpoint: str
    device: str
    filesystem: str
    total: int = 0
    used: int = 0
    free: int = 0
    usage: float | None = None
    note: str = ""


@dataclass(frozen=True)
class SensorInfo:
    name: str
    temperature: float
    high: float | None = None
    critical: float | None = None


@dataclass(frozen=True)
class BatteryInfo:
    percent: float
    plugged: bool
    remaining: int | None = None


@dataclass(frozen=True)
class GPUInfo:
    key: str
    name: str
    utilization: float | None = None
    used: int | None = None
    total: int | None = None
    temperature: float | None = None
    power: float | None = None
    fan: float | None = None
    note: str = ""


@dataclass(frozen=True)
class PortInfo:
    protocol: str
    address: str
    port: int
    pid: int | None
    name: str
    description: str
    created: float | None = None

    @property
    def key(self) -> tuple:
        return self.protocol, self.address, self.port, self.pid, self.created

    @property
    def endpoint(self) -> str:
        host = f"[{self.address}]" if ":" in self.address else self.address
        return f"{host}:{self.port}"

    @property
    def scope(self) -> str:
        try:
            ip = ipaddress.ip_address(self.address.split("%", 1)[0])
            return "local" if ip.is_loopback else "any" if ip.is_unspecified else "specific"
        except ValueError:
            return "specific"


@dataclass(frozen=True)
class Snapshot:
    timestamp: float
    wall_time: float
    cpu: float | None
    cores: int
    frequency: float | None
    cpu_temperature: float | None
    memory_total: int
    memory_available: int
    swap_used: int
    swap_total: int
    network: str
    interfaces: tuple[str, ...]
    download: float | None
    upload: float | None
    disk_used: int
    disk_total: int
    disk_read: float | None
    disk_write: float | None
    gpus: tuple[GPUInfo, ...]
    processes: tuple[ProcessInfo, ...]
    uptime: float
    duration: float
    gpu_note: str = ""
    hardware: HardwareInfo = field(default_factory=HardwareInfo)
    cpu_per_core: tuple[float | None, ...] = ()
    load_average: tuple[float, ...] = ()
    memory_cached: int | None = None
    memory_buffers: int | None = None
    memory_free: int | None = None
    network_details: tuple[NetworkInfo, ...] = ()
    disks: tuple[DiskInfo, ...] = ()
    partitions: tuple[PartitionInfo, ...] = ()
    sensors: tuple[SensorInfo, ...] = ()
    battery: BatteryInfo | None = None

    @property
    def memory_used(self) -> int:
        return max(0, self.memory_total - self.memory_available)

    @property
    def memory_percent(self) -> float:
        return self.memory_used / self.memory_total * 100 if self.memory_total else 0


def size(value: float | int | None, precision: int = 1) -> str:
    if value is None:
        return "—"
    value = max(0.0, float(value))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.{precision}f} {unit}"
        value /= 1024
    return "—"


def percent(value: float | None) -> str:
    return "采样中" if value is None else f"{value:.1f}%"


def rate(value: float | None) -> str:
    return "采样中" if value is None else size(value) + "/s"
