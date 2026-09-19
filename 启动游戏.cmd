@echo off
cd /d "%~dp0"
python -X utf8 -m game.server --port 8766
pause
