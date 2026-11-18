from types import SimpleNamespace as Record
import socket

import psutil

from pulse_monitor.telemetry import Telemetry


def test_network_counter_reset_hotplug_and_link_metadata(monkeypatch):
    telemetry = Telemetry()
    monkeypatch.setattr(psutil, 'net_if_stats', lambda: {'eth0': Record(isup=True, speed=1000, mtu=1500)})
    monkeypatch.setattr(psutil, 'net_if_addrs', lambda: {'eth0': [Record(family=socket.AF_INET, address='192.0.2.2')]})
    old = Record(bytes_recv=100, bytes_sent=50)
    now = Record(bytes_recv=300, bytes_sent=10, packets_recv=3, packets_sent=1,
                 errin=0, errout=1, dropin=2, dropout=0)
    rows = telemetry.networks({'eth0': now, 'new0': now}, {'eth0': old}, 2)
    assert rows[0].download == 100
    assert rows[0].upload is None
    assert rows[0].ipv4 == ('192.0.2.2',) and rows[0].speed == 1000
    assert rows[0].errors == 1 and rows[0].dropped == 2
    assert rows[1].download is None and rows[1].is_up is None


def test_disk_device_rates_busy_time_and_reset(monkeypatch):
    telemetry = Telemetry()
    old = Record(read_bytes=100, write_bytes=100, read_count=10, write_count=10, busy_time=10)
    now = Record(read_bytes=300, write_bytes=50, read_count=20, write_count=15, busy_time=1010)
    monkeypatch.setattr(psutil, 'disk_io_counters', lambda **kw: {'deviceA': now, 'loop123': now})
    telemetry.previous_disks = {'deviceA': old}
    rows = telemetry.disk_devices(2)
    assert len(rows) == 1
    assert rows[0].read_rate == 100 and rows[0].write_rate is None
    assert rows[0].read_iops == 5 and rows[0].busy == 50
    telemetry.reset()
    assert telemetry.disk_devices(0)[0].read_rate is None


def test_partition_cache_excludes_remote_and_keeps_unreadable_mount(monkeypatch):
    telemetry = Telemetry()
    mounts = [Record(mountpoint='/data', device='/dev/test', fstype='ext4'),
              Record(mountpoint='/remote', device='server:/data', fstype='nfs4')]
    monkeypatch.setattr(psutil, 'disk_partitions', lambda **kw: mounts)
    calls = []
    def usage(path):
        calls.append(path)
        raise PermissionError(path)
    monkeypatch.setattr(psutil, 'disk_usage', usage)
    root = Record(total=100, used=25, free=70, percent=25)
    first = telemetry.mounted_partitions(root)
    assert calls == ['/data']
    assert first[0].mountpoint == '/' and first[0].usage == 25
    assert first[1].mountpoint == '/data' and first[1].usage is None
    assert telemetry.mounted_partitions(root) is first
    assert calls == ['/data']
