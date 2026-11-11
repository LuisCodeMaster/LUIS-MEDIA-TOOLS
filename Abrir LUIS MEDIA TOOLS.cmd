@echo off
rem Abre o app LUIS MEDIA TOOLS (janela, sem console).
cd /d "%~dp0"
if exist "LUIS MEDIA TOOLS\LUIS MEDIA TOOLS.exe" (
  start "" "LUIS MEDIA TOOLS\LUIS MEDIA TOOLS.exe"
  exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
  echo Primeira vez? De dois cliques em "Instalar.cmd" antes.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m luismedia.gui
