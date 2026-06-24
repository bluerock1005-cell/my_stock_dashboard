# stock_monitor_gui.spec
# 使用方法：在项目目录下运行
#   pyinstaller stock_monitor_gui.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ---- akshare 数据文件 ----
akshare_datas = collect_data_files("akshare")

# ---- certifi SSL 证书（缺了 HTTPS 请求全部失败） ----
certifi_datas = collect_data_files("certifi")

# ---- 隐式依赖：akshare 用到的网络/解析库 ----
hidden = (
    collect_submodules("akshare") +
    collect_submodules("multitasking") +
    collect_submodules("pandas") +
    collect_submodules("PyQt6") +
    collect_submodules("requests") +
    collect_submodules("urllib3") +
    collect_submodules("charset_normalizer") +
    collect_submodules("curl_cffi") +
    collect_submodules("lxml") +
    [
        # pandas 内部 C 扩展
        "pandas._libs.tslibs.np_datetime",
        "pandas._libs.tslibs.nattype",
        "pandas._libs.tslibs.timedeltas",
        "pandas._libs.tslibs.offsets",
        "pandas._libs.skiplist",
        # 并发
        "concurrent.futures",
    ]
)

a = Analysis(
    ["gui.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("watchlist.json", "."),
        *akshare_datas,
        *certifi_datas,
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy",
        "IPython", "jupyter", "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="股票监控",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="股票监控",
)
