@echo off
rem Abre a interface do LUIS MEDIA TOOLS com dois cliques (sem mexer na politica de execucao do Windows).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" if not exist "motor\luismedia.exe" (
  echo Primeira vez? Rode "Instalar.cmd" antes.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pipeline-completo.ps1"
