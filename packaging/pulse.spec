# Build on Ubuntu 24.04 x86_64 with Python 3.12 in an isolated environment.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ROOT = Path(SPECPATH).parent
datas = [(str(ROOT / "pulse_monitor" / "assets"), "pulse_monitor/assets")]
datas += collect_data_files("qfluentwidgets")
for package in ("PySide6-Fluent-Widgets", "pyqtgraph", "psutil", "nvidia-ml-py"):
    datas += copy_metadata(package)

a = Analysis(
    [str(ROOT / "scripts" / "frozen_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["pynvml", "PySide6.QtSvg"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "matplotlib", "scipy", "IPython",
              "jupyter", "pytest", "tkinter"],
    noarchive=False,
)
# GPU driver libraries must come from the target machine, never from the builder.
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.startswith("libnvidia-")]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PulseMonitor",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PulseMonitor")
