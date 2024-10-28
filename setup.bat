@echo off
echo Setting up virtual environment...

:: Create virtual environment if it doesn't exist
if not exist venv (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

:: Run the main script
call run.bat