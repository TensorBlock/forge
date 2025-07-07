@echo off
echo === Forge Middleware Setup ===
echo.

REM Check if Python 3.12 is installed
where python3.12 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python 3.12 is not installed or not in PATH. Please install Python 3.12 or newer.
    echo.
    echo Windows installation options:
    echo.
    echo Option 1: Download from Python.org
    echo   Visit: https://www.python.org/downloads/
    echo   Download Python 3.12 and run the installer
    echo   Make sure to check "Add Python to PATH" during installation
    echo.
    echo Option 2: Install with winget (Windows 10/11)
    echo   Run: winget install Python.Python.3.12
    echo.
    echo Option 3: Install with Chocolatey
    echo   Run: choco install python312
    echo.
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%V in ('python3.12 --version 2^>^&1') do (
    echo Using Python version: %%V
)

REM Check if PostgreSQL is installed
where psql >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: PostgreSQL is not installed or not in PATH.
    echo.
    echo Windows installation options:
    echo.
    echo Option 1: Download from PostgreSQL.org
    echo   Visit: https://www.postgresql.org/download/windows/
    echo   Download and run the installer
    echo   Make sure to note down the password you set for postgres user
    echo.
    echo Option 2: Install with winget (Windows 10/11)
    echo   Run: winget install PostgreSQL.PostgreSQL
    echo.
    echo Option 3: Install with Chocolatey
    echo   Run: choco install postgresql
    echo.
    exit /b 1
)

REM Check if PostgreSQL service is running
sc query postgresql >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: PostgreSQL service is not running.
    echo.
    echo Please start the PostgreSQL service:
    echo 1. Open Services (services.msc)
    echo 2. Find "postgresql-x64-XX" (where XX is your version)
    echo 3. Right-click and select "Start"
    echo.
    echo Or run in Command Prompt as Administrator:
    echo net start postgresql-x64-XX
    echo.
    exit /b 1
)

echo PostgreSQL is installed and running.

REM Install UV if not installed
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo UV package manager not found. Installing UV...

    REM Install UV using pip
    python3.12 -m pip install uv

    REM Add uv to the PATH for this session
    set PATH=%USERPROFILE%\.local\bin;%PATH%

    echo UV installed.
) else (
    echo UV package manager already installed.
)

REM Create virtual environment
echo.
echo Creating virtual environment...
if exist .venv\ (
    echo Virtual environment already exists. Using existing .venv.
) else (
    uv venv .venv --python=python3.12
    echo Virtual environment created.
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call .venv\Scripts\activate
echo Virtual environment activated.

REM Install dependencies
echo.
echo Installing dependencies...

echo Installing project dependencies from pyproject.toml...
uv pip install -e .
if %ERRORLEVEL% neq 0 (
    echo Error installing project dependencies.
    echo If you see an error about 'Unable to determine which files to ship inside the wheel',
    echo make sure your pyproject.toml file has the [tool.hatch.build.targets.wheel] section
    echo with packages = ["app"] to specify where your package code is located.
    exit /b 1
)

echo Installing development dependencies...
uv pip install -e ".[dev]"
if %ERRORLEVEL% neq 0 (
    echo Error installing development dependencies.
    exit /b 1
)

echo Dependencies installed.

REM Create .env file if it doesn't exist
if not exist .env (
    echo.
    echo Creating .env file from example...
    copy .env.example .env
    echo Please edit .env file to add your API keys and other configuration.
) else (
    echo.
    echo .env file already exists. Keeping existing configuration.
)

REM Database setup
echo.
echo Setting up PostgreSQL database...

REM Check if database exists
psql -l | findstr /C:"forge" >nul
if %ERRORLEVEL% equ 0 (
    echo Database 'forge' already exists.
    echo.
    echo Choose an option:
    echo 1) Drop and recreate database (will delete all data)
    echo 2) Keep existing database
    set /p db_choice="Enter your choice (1-2) [2]: "

    if "%db_choice%"=="1" (
        echo Dropping existing database...
        dropdb forge
        echo Database dropped.
    ) else (
        echo Keeping existing database.
    )
)

REM Create database if it doesn't exist
psql -l | findstr /C:"forge" >nul
if %ERRORLEVEL% neq 0 (
    echo Creating new database...
    createdb forge
    echo Database created.
)

REM Run database migrations
echo.
echo Running database migrations...
alembic upgrade head
echo Database migrations complete.

echo.
echo === Setup Complete! ===
echo.
echo IMPORTANT: Virtual Environment
echo This script has activated the virtual environment for the current window only.
echo If you open a new command prompt, you must manually activate the virtual environment:
echo .venv\Scripts\activate
echo You can tell the virtual environment is active when you see (.venv) at the beginning of your prompt.
echo.
echo Next Steps:
echo 1. Ensure your virtual environment is active (.venv)
echo 2. You can run the server with: python run.py
echo    Or with uvicorn directly: uvicorn app.main:app --reload
echo 3. Run tests with: python tests\run_tests.py
echo.
echo Remember to edit your .env file to add your API keys!
echo.

REM Keep the command window open
pause
