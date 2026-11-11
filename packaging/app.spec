# PyInstaller: gera "dist/LUIS MEDIA TOOLS/LUIS MEDIA TOOLS.exe" (app com janela, sem console).
# Uso: python -m PyInstaller --noconfirm --clean packaging/app.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = collect_submodules("luismedia") + collect_submodules("faster_whisper")
datas = (collect_data_files("faster_whisper")
         + collect_data_files("luismedia", includes=["gui/assets/*", "profiles/*.yaml"]))

a = Analysis(
    ["app_entry.py"],
    pathex=["../src"],
    hiddenimports=hidden,
    datas=datas,
    excludes=["tkinter", "matplotlib", "pytest", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LUIS MEDIA TOOLS", console=False,
          icon="../src/luismedia/gui/assets/icon.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="LUIS MEDIA TOOLS")
