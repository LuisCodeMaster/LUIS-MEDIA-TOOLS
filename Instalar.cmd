@echo off
rem Instala ou atualiza o LUIS MEDIA TOOLS (Python, motor, Whisper, FFmpeg, Ollama).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
pause
