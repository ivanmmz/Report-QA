@echo off
:: Lock working directory to the script's own folder (handles moved/renamed folders)
cd /d "%~dp0"
chcp 65001 >nul
cls
title Report QA - RAG System

:: ============================================
:: Report QA - Tauri Launcher
:: ============================================

echo.
echo ============================================
echo    Report QA - RAG System
echo    PDF Intelligence + AI Chat + Reports
echo ============================================
echo.

:: Navigate to tauri-ui directory
if not exist "..\tauri-ui\package.json" (
    echo [ERROR] tauri-ui directory not found.
    echo Please ensure the tauri-ui folder exists in the project root.
    pause
    exit /b 1
)

cd /d "%~dp0..\tauri-ui"

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js 18 or higher.
    pause
    exit /b 1
)

echo [OK] Node.js detected.

:: Check npm dependencies
if not exist "node_modules" (
    echo [INFO] Installing npm dependencies...
    npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install npm dependencies.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed.
)

echo.
echo ============================================
echo    Starting Tauri Dev Server...
echo    Close this window or press Ctrl+C to stop
echo ============================================
echo.

:: Launch Tauri dev server
npm run tauri dev

:: Check exit code
if errorlevel 1 (
    echo.
    echo [ERROR] Tauri exited with error, exit code = %errorlevel%
    pause
)
