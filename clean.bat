@echo off
echo Cleaning up environment...

:: Deactivate virtual environment if active
call venv\Scripts\deactivate.bat 2>nul

:: Remove virtual environment
if exist venv (
    echo Removing virtual environment...
    rmdir /s /q venv
)

:: Remove any cached files
if exist __pycache__ (
    echo Removing Python cache...
    rmdir /s /q __pycache__
)

echo Cleanup complete.
pause