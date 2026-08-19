# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

pyqtgraph_datas = collect_data_files(
    'pyqtgraph', includes=['colors/maps/*.csv', 'icons/**']
)
smc_helper = 'src/pc_diagnostic/providers/smc_helper'
native_binaries = (
    [(smc_helper, 'pc_diagnostic/providers')] if os.path.exists(smc_helper) else []
)

a = Analysis(
    ['src/pc_diagnostic/main.py'],
    pathex=[],
    binaries=native_binaries,
    datas=pyqtgraph_datas,
    hiddenimports=[
        'psutil',
        'rich',
        'crewai',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
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
    name='pc_diagnostic',
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
)
