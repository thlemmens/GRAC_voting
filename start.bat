@echo off
cd /d "%~dp0"
echo Starting Group Allocator...
call .venv\Scripts\activate.bat
start "" http://localhost:3000/admin.html
python server.py
pause
