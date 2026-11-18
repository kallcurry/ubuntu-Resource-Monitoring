"""Read-only detailed Linux telemetry; called exclusively from the worker."""

from pathlib import Path
import os
import platform
import socket
import time

import psutil

from .data import BatteryInfo, DiskInfo, HardwareInfo, NetworkInfo, PartitionInfo, SensorInfo


def delta(current, previous, elapsed):
    if previous is None or elapsed <= 0 or current < previous:
        return None
    return (current - previous) / elapsed


class Telemetry:
    def __init__(self):
        model = platform.processor() or "型号不可读"
        try:
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                key, _, value = line.partition(':')
                if key.strip() in ('model name', 'Hardware') and value.strip():
                    model = value.strip()
                    break
        except OSError:
            pass
        try:
            distribution = platform.freedesktop_os_release().get('PRETTY_NAME', 'Linux')
        except OSError:
            distribution = 'Linux'
        self.hardware = HardwareInfo(model, psutil.cpu_count(logical=False), distribution,
                                     platform.release(), platform.machine())
        self.previous_disks = {}
        self.partitions = ()
        self.next_partitions = 0

    def reset(self):
        self.previous_disks.clear()

    def networks(self, counters, previous, elapsed):
        try:
            stats = psutil.net_if_stats()
            addresses = psutil.net_if_addrs()
        except (OSError, psutil.Error):
            stats, addresses = {}, {}
        rows = []
        for name, item in counters.items():
            old = previous.get(name)
            state = stats.get(name)
            addrs = addresses.get(name, ())
            ipv4 = tuple(a.address for a in addrs if a.family == socket.AF_INET)
            ipv6 = tuple(a.address for a in addrs if a.family == socket.AF_INET6)
            mac = next((a.address for a in addrs if a.family == psutil.AF_LINK), '—')
            rows.append(NetworkInfo(
                name, state.isup if state else None,
                state.speed if state and state.speed > 0 else None,
                state.mtu if state else None, ipv4, ipv6, mac,
                delta(item.bytes_recv, old.bytes_recv if old else None, elapsed),
                delta(item.bytes_sent, old.bytes_sent if old else None, elapsed),
                item.bytes_recv, item.bytes_sent, item.packets_recv, item.packets_sent,
                item.errin + item.errout, item.dropin + item.dropout))
        return tuple(rows)

    def disk_devices(self, elapsed):
        try:
            counters = psutil.disk_io_counters(perdisk=True) or {}
        except (OSError, psutil.Error):
            counters = {}
        rows = []
        for name, item in counters.items():
            if name.startswith(('loop', 'ram', 'zram', 'fd', 'sr')):
                continue
            if (Path('/sys/class/block') / name / 'partition').exists():
                continue
            old = self.previous_disks.get(name)

            def change(field):
                current = getattr(item, field, None)
                prior = getattr(old, field, None)
                return delta(current, prior, elapsed) if current is not None else None

            busy = change('busy_time')
            rows.append(DiskInfo(name, change('read_bytes'), change('write_bytes'),
                                 change('read_count'), change('write_count'),
                                 min(100, busy / 10) if busy is not None else None))
        self.previous_disks = counters
        return tuple(rows)

    def mounted_partitions(self, root_usage):
        if time.monotonic() < self.next_partitions:
            return self.partitions
        local_filesystems = {'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'vfat', 'exfat',
                             'ntfs', 'ntfs3', 'zfs', 'f2fs', 'bcachefs', 'overlay'}
        rows = {}
        try:
            mounts = psutil.disk_partitions(all=False)
        except (OSError, psutil.Error):
            mounts = ()
        for part in mounts:
            if part.mountpoint != '/' and part.fstype not in local_filesystems:
                continue
            try:
                usage = root_usage if part.mountpoint == '/' else psutil.disk_usage(part.mountpoint)
                row = PartitionInfo(part.mountpoint, part.device, part.fstype,
                                    usage.total, usage.used, usage.free, usage.percent)
            except (OSError, psutil.Error):
                row = PartitionInfo(part.mountpoint, part.device, part.fstype, note='不可读或挂载已移除')
            rows[part.mountpoint] = row
        if '/' not in rows:
            rows['/'] = PartitionInfo('/', '根文件系统', '—', root_usage.total, root_usage.used,
                                      root_usage.free, root_usage.percent)
        self.partitions = tuple(rows[key] for key in sorted(rows))
        self.next_partitions = time.monotonic() + 15
        return self.partitions

    def collect(self, memory, networks, previous_networks, elapsed, root_usage):
        try:
            cores = tuple(psutil.cpu_percent(interval=None, percpu=True))
            if elapsed <= 0:
                cores = tuple(None for _ in cores)
        except (OSError, psutil.Error):
            cores = ()
        try:
            load = tuple(os.getloadavg())
        except OSError:
            load = ()
        sensors = []
        try:
            for group, records in psutil.sensors_temperatures().items():
                for index, sensor in enumerate(records):
                    if sensor.current is not None:
                        sensors.append(SensorInfo(f'{group} · {sensor.label or index + 1}',
                                                  sensor.current, sensor.high, sensor.critical))
        except (OSError, AttributeError, psutil.Error):
            pass
        battery = None
        try:
            raw = psutil.sensors_battery()
            if raw:
                battery = BatteryInfo(raw.percent, raw.power_plugged,
                                      raw.secsleft if raw.secsleft > 0 else None)
        except (OSError, AttributeError, psutil.Error):
            pass
        return dict(hardware=self.hardware, cpu_per_core=cores, load_average=load,
                    memory_cached=getattr(memory, 'cached', None),
                    memory_buffers=getattr(memory, 'buffers', None),
                    memory_free=getattr(memory, 'free', None),
                    network_details=self.networks(networks, previous_networks, elapsed),
                    disks=self.disk_devices(elapsed), partitions=self.mounted_partitions(root_usage),
                    sensors=tuple(sensors), battery=battery)
