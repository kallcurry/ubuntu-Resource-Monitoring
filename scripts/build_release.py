"""Build a standalone Qt bundle, .deb installer, portable archive and checksums."""

import hashlib
import importlib.metadata
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments):
    subprocess.run([str(a) for a in arguments], cwd=ROOT, check=True)


def copy_licenses(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, destination / name)
    distributions = sorted(importlib.metadata.distributions(),
                           key=lambda d: d.metadata.get("Name", "").casefold())
    versions = []
    for distribution in distributions:
        name = distribution.metadata.get("Name", "unknown")
        versions.append(f"{name}=={distribution.version}")
        for item in distribution.files or ():
            relative = Path(str(item))
            lower = str(relative).lower()
            if (".dist-info/" not in lower or
                    not any(word in lower for word in ("license", "copying", "notice")) or
                    ".." in relative.parts or relative.is_absolute()):
                continue
            source = Path(distribution.locate_file(item))
            if source.is_file():
                target = destination / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    (destination / "BUILD_DEPENDENCIES.txt").write_text("\n".join(versions) + "\n")


def main():
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
        raise SystemExit("Release builder currently targets Ubuntu 24.04 x86_64 only")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    run(sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        "--distpath", ROOT / "dist", "--workpath", ROOT / "build/pyinstaller",
        ROOT / "packaging/pulse.spec")
    bundle = ROOT / "dist/PulseMonitor"
    copy_licenses(bundle / "licenses")
    shutil.copy2(ROOT / "README.md", bundle / "README.md")
    portable = output / f"pulse-monitor-{version}-linux-x86_64.tar.gz"
    with tarfile.open(portable, "w:gz", compresslevel=6) as archive:
        archive.add(bundle, arcname="PulseMonitor")

    stage = ROOT / "build/debian"
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "DEBIAN").mkdir(parents=True)
    shutil.copytree(bundle, stage / "opt/pulse-monitor", symlinks=True)
    for relative in ("usr/bin", "usr/share/applications", "usr/share/icons/hicolor/scalable/apps",
                     "usr/share/doc/pulse-monitor"):
        (stage / relative).mkdir(parents=True)
    launcher = stage / "usr/bin/pulse-monitor"
    shutil.copy2(ROOT / "packaging/launcher.sh", launcher)
    launcher.chmod(0o755)
    shutil.copy2(ROOT / "packaging/pulse-monitor.desktop",
                 stage / "usr/share/applications/pulse-monitor.desktop")
    shutil.copy2(ROOT / "pulse_monitor/assets/pulse.svg",
                 stage / "usr/share/icons/hicolor/scalable/apps/pulse-monitor.svg")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md"):
        shutil.copy2(ROOT / name, stage / "usr/share/doc/pulse-monitor" / name)
    installed_kib = sum(p.stat().st_size for p in stage.rglob("*")
                        if p.is_file() and not p.is_symlink()) // 1024
    dependencies = (
        "libc6 (>= 2.39), libstdc++6, libgcc-s1, libgl1, libegl1, libopengl0, "
        "libfontconfig1, libfreetype6, libdbus-1-3, libglib2.0-0t64, libsm6, libice6, "
        "libx11-6, libx11-xcb1, libxext6, libxrender1, libxcb1, libxcb-cursor0, "
        "libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, "
        "libxcb-shape0, libxcb-xfixes0, libxcb-randr0, libxcb-render0, libxcb-shm0, "
        "libxcb-sync1, libxcb-xkb1, libxcb-util1, libxkbcommon0, libxkbcommon-x11-0"
    )
    control = (
        "Package: pulse-monitor\n"
        f"Version: {version}\n"
        "Architecture: amd64\n"
        "Section: utils\nPriority: optional\n"
        "Maintainer: Pulse Monitor contributors <noreply@github.com>\n"
        f"Installed-Size: {installed_kib}\n"
        f"Depends: {dependencies}\n"
        "Homepage: https://github.com/kallcurry/ubuntu-Resource-Monitoring\n"
        "Description: Native Ubuntu hardware, process and local port monitor\n"
        " Rounded Qt desktop UI with Chinese process descriptions and GPU monitoring.\n"
        " Includes its Python and Qt runtime. Targets Ubuntu 24.04 amd64.\n"
    )
    (stage / "DEBIAN/control").write_text(control)
    run("desktop-file-validate", stage / "usr/share/applications/pulse-monitor.desktop")
    deb = output / f"pulse-monitor_{version}_amd64.deb"
    run("dpkg-deb", "--root-owner-group", "--build", "--uniform-compression", "-Zxz", "-z6", stage, deb)
    checksums = output / "SHA256SUMS"
    checksums.write_text("".join(
        f"{hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()}  {path.name}\n"
        for path in (deb, portable)
    ))
    print(f"Built {deb.name} and {portable.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
