@echo off
chcp 65001 >nul
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\switch-tier.ps1" -Tier 600
if errorlevel 1 pause
