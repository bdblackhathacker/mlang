# PyInstaller spec: Linux onefile CLI (build on Linux).
# Windows .exe MUST be built on Windows (PyInstaller can't cross-compile).
#   On Windows: pip install pyinstaller pillow
#               python package\assets\make_icon.py   (with logo.png present)
#               pyinstaller --noconfirm --onefile --name mlang --icon package\assets\icon.ico mlang\cli.py
#   On Linux:   pip install pyinstaller
#               pyinstaller --noconfirm --onefile --name mlang mlang/cli.py
# Output: dist/mlang
# -*- mode: python ; coding: utf-8 -*-
block_cipher = None
a = Analysis(
    ['../../cli.py'],
    pathex=['../../src'],
    binaries=[],
    datas=[('../../examples', 'examples'), ('../../grammar.ebnf', '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='mlang',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    # icon='../assets/icon.ico',  # uncomment on Windows after make_icon.py
)
