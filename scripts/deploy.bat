@echo off
REM Deployment script for Anime AI Character system on Windows
REM Usage: deploy.bat [command] [options]

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    exit /b 1
)

REM Parse command line arguments
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=help

if "%COMMAND%"=="help" goto :help
if "%COMMAND%"=="validate" goto :validate
if "%COMMAND%"=="build" goto :build
if "%COMMAND%"=="start" goto :start
if "%COMMAND%"=="stop" goto :stop
if "%COMMAND%"=="restart" goto :restart
if "%COMMAND%"=="status" goto :status
if "%COMMAND%"=="logs" goto :logs
if "%COMMAND%"=="cleanup" goto :cleanup
if "%COMMAND%"=="deploy" goto :deploy

echo ❌ Unknown command: %COMMAND%
goto :help

:help
echo.
echo 🎭 Anime AI Character Deployment Script
echo =====================================
echo.
echo Usage: deploy.bat [command]
echo.
echo Commands:
echo   validate  - Validate configuration and prerequisites
echo   build     - Build Docker images
echo   start     - Start services
echo   stop      - Stop services
echo   restart   - Restart services
echo   status    - Show service status
echo   logs      - Show service logs
echo   cleanup   - Clean up Docker resources
echo   deploy    - Full deployment (validate + build + start)
echo   help      - Show this help
echo.
goto :end

:validate
echo 🔍 Validating configuration...
python scripts\validate_config.py
if errorlevel 1 (
    echo ❌ Configuration validation failed
    exit /b 1
)
echo ✅ Configuration validation passed
goto :end

:build
echo 🔨 Building Docker images...
docker compose build
if errorlevel 1 (
    echo ❌ Docker build failed
    exit /b 1
)
echo ✅ Docker images built successfully
goto :end

:start
echo 🚀 Starting services...
docker compose up -d
if errorlevel 1 (
    echo ❌ Failed to start services
    exit /b 1
)
echo ✅ Services started successfully
echo 🌐 Access the application at: http://localhost:5000
goto :status

:stop
echo 🛑 Stopping services...
docker compose down
if errorlevel 1 (
    echo ❌ Failed to stop services
    exit /b 1
)
echo ✅ Services stopped successfully
goto :end

:restart
echo 🔄 Restarting services...
docker compose restart
if errorlevel 1 (
    echo ❌ Failed to restart services
    exit /b 1
)
echo ✅ Services restarted successfully
goto :end

:status
echo 📊 Service status:
docker compose ps
goto :end

:logs
echo 📝 Service logs:
docker compose logs
goto :end

:cleanup
echo 🧹 Cleaning up Docker resources...
docker compose down --rmi all --volumes
echo ✅ Cleanup completed
goto :end

:deploy
echo 🎬 Starting full deployment...
echo.

REM Step 1: Validate
echo Step 1/3: Validating configuration...
call :validate
if errorlevel 1 exit /b 1

REM Step 2: Build
echo.
echo Step 2/3: Building Docker images...
call :build
if errorlevel 1 exit /b 1

REM Step 3: Start
echo.
echo Step 3/3: Starting services...
call :start
if errorlevel 1 exit /b 1

echo.
echo ✅ Deployment completed successfully!
echo 🌐 Access the application at: http://localhost:5000
goto :end

:end
endlocal