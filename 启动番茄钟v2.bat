@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "pomodoro_widget_v2.py") || (start "" python "pomodoro_widget_v2.py")
