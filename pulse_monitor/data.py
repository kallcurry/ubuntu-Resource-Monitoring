"""Immutable snapshots shared between the collection thread and the UI."""

from dataclasses import dataclass
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

    @property
    def key(self) -> tuple[int, float | None]:
        return self.pid, self.created


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
