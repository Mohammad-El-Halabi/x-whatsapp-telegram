# -*- mode: python ; coding: utf-8 -*-

a = Analysis(['main.py'], pathex=[], binaries=[], datas=[], hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='telegram-sidecar', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=True)
