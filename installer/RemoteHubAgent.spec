# -*- mode: python -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    "PySide6",
    "agent",
    "agent.client",
    "agent.config",
    "agent.security",
    "agent.commands",
    "agent.commands.media_web",
    "agent.commands.screenshot",
    "agent.commands.system",
]

for pkg in ['pyautogui', 'plyer', 'psutil', 'win32com']:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [
        '../agent/gui.py'
    ],
    pathex=['..'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="RemoteHubAgent",
    console=False,
    icon="icon.ico"
)