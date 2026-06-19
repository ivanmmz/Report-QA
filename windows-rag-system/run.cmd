@echo off
:: Lock working directory to the script's own folder (handles moved/renamed folders)
cd /d "%~dp0"
chcp 65001 >nul
cls
title Windows RAG System

:: ============================================
:: Windows Local RAG System - One-Click Launcher
:: ============================================

echo.
echo ============================================
echo    Windows Local RAG System
echo    PDF Intelligence + AI Chat + Reports
echo ============================================
echo.

:: Check app.py
if not exist "app.py" (
    echo [ERROR] app.py not found.
    echo Please run this script from the project root folder.
    pause
    exit /b 1
)

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11 or higher.
    pause
    exit /b 1
)

echo [OK] Python detected.

:: Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)

:: Activate environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate

:: Check dependencies
echo [INFO] Checking dependencies...
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

:: Create required directories
if not exist "data\documents" mkdir "data\documents"
if not exist "data\uploads" mkdir "data\uploads"
if not exist "data\vectors" mkdir "data\vectors"
if not exist "data\metadata" mkdir "data\metadata"

echo.
echo ============================================
echo    Starting Streamlit App...
echo    Open http://localhost:8501 in browser
echo    Close this window or press Ctrl+C to stop
echo ============================================
echo.

:: Launch Streamlit (use "python -m" instead of the streamlit.exe launcher,
:: which bakes in the venv path at creation time and breaks if the folder is moved)
python -m streamlit run app.py

:: Check exit code
if errorlevel 1 (
    echo.
    echo [ERROR] Streamlit exited with error, exit code = %errorlevel%
    pause
)

:: Deactivate venv
deactivate
