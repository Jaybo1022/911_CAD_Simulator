@echo off
echo Starting 911 CAD Simulator...
echo.

REM Check if Python is installed
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    py -m venv venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

REM Initialize database
echo Initializing database...
py database\init_db.py
if %errorlevel% neq 0 (
    echo Failed to initialize database.
    pause
    exit /b 1
)

REM Add sample data
echo Adding sample data...
py database\add_sample_data.py

REM Import run cards from Excel
echo Importing run cards from Excel...
py database\import_run_cards.py

REM Start the server
echo.
echo Starting FastAPI server...
echo The application will be available at: http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo.
py backend\main.py
