@echo off
echo Starting application setup and deployment...

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

:: Install requirements
echo Installing requirements...
pip install -r requirements.txt

:: Run the application
echo Starting the application...
python run_waitress.py

:: Keep the window open if there's an error
if %ERRORLEVEL% neq 0 (
    echo An error occurred. Press any key to exit.
    pause
)