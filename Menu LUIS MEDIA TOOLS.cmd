@echo off
rem Abre o menu com todas as ferramentas (slides, diagnostico, modulos individuais).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0luis-media.ps1"
