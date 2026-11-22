# PyInstaller: gera dist/luismedia/luismedia.exe (modo onedir, inicia rapido).
# Uso: python -m PyInstaller --noconfirm --clean packaging/luismedia.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = collect_submodules("luismedia") + collect_submodules("faster_whisper")
datas = (collect_data_files("faster_whisper")  # assets do VAD (silero)
         + collect_data_files("luismedia", includes=["profiles/*.yaml", "assets/fonts/*", "assets/emoji/*"]))

a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    hiddenimports=hidden,
    datas=datas,
    excludes=["tkinter", "matplotlib", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="luismedia", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="luismedia")
