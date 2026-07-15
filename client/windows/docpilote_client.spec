# -*- mode: python -*-
a = Analysis(
    ['docpilote_client.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'requests'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='docpilote_client',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='../../packaging/assets/docpilote.ico',
)
