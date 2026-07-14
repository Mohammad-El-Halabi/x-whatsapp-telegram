# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'telethon',
        'telethon.tl',
        'telethon.tl.types',
        'telethon.tl.functions',
        'telethon.network',
        'telethon.crypto',
        'telethon.sessions',
        'pyside6',
        'pyside6.QtWidgets',
        'pyside6.QtCore',
        'pyside6.QtGui',
        'supabase',
        'supabase._sync',
        'supabase._async',
        'apscheduler',
        'apscheduler.schedulers',
        'apscheduler.schedulers.asyncio',
        'apscheduler.triggers',
        'apscheduler.triggers.cron',
        'pydantic',
        'dotenv',
        'aiohttp',
        'qrcode',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TelegramStaffControl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
