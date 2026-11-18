# 第三方组件

项目源码不直接复制下列第三方库代码；安装时从其发行包获取。许可证文件随第三方发行包提供。

| 组件 | 作用 | 上游许可证 / 官方链接 |
|---|---|---|
| PySide6 / Qt | 原生窗口与控件 | LGPLv3 / GPLv3 / 商业授权，依模块而定；[Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html) |
| PySide6-Fluent-Widgets | Fluent 按钮、输入、设置、提示等 | GPLv3；[官方项目](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) |
| PySideSix-Frameless-Window | Fluent 库的传递依赖 | 见安装包许可证；[官方项目](https://github.com/zhiyiYo/PyQt-Frameless-Window) |
| pyqtgraph | 实时曲线 | MIT；[官方项目](https://github.com/pyqtgraph/pyqtgraph) |
| numpy | 图表数组处理，传递依赖 | BSD-3-Clause；[官方项目](https://numpy.org/) |
| psutil | 系统与进程采集 | BSD-3-Clause；[官方项目](https://github.com/giampaolo/psutil) |
| nvidia-ml-py | NVML Python 绑定 | BSD；[官方发行页](https://pypi.org/project/nvidia-ml-py/) |
| Lucide | 仅用于浏览器设计原型 | ISC；[官方项目](https://github.com/lucide-icons/lucide) |
| PyInstaller | 安装包的解释器启动器与打包工具 | GPLv2 或更新版及其分发例外；[官方许可说明](https://pyinstaller.org/en/stable/license.html) |

应用图标为本项目创建的简单脉冲线条图形。NVIDIA 硬件与驱动通过系统 NVML 接口访问，项目不包含驱动。

安装包同时包含 `licenses/`，保存构建环境中的第三方发行包许可文件和版本清单。与每个 Release 对应的完整项目源码可从同名版本标签取得。
