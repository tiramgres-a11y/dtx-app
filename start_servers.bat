@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM start_servers.bat — DTx Development Environment Launcher (Windows)
REM
REM Double-click this file, or run from PowerShell:
REM   .\start_servers.bat
REM
REM Opens two new Command Prompt windows:
REM   Window 1 → FastAPI backend  (http://localhost:8000)
REM   Window 2 → Expo frontend    (QR code + browser)
REM
REM Prerequisites (run once in PowerShell):
REM   pip install -r backend\requirements.txt
REM   cd frontend; npm install
REM ─────────────────────────────────────────────────────────────────────────────

SET ROOT=%~dp0

echo.
echo ============================================================
echo   DTx Development Environment — Starting both servers
echo ============================================================
echo.
echo   Backend  → http://localhost:8000
echo   API Docs → http://localhost:8000/docs
echo   Frontend → Expo DevTools (browser + QR code)
echo.

REM ── Window 1: FastAPI Backend ────────────────────────────────────────────────
start "DTx Backend — FastAPI :8000" cmd /k "cd /d "%ROOT%" && echo. && echo  FastAPI Backend starting... && echo  API docs: http://localhost:8000/docs && echo. && python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"

REM ── Window 2: Expo Frontend ──────────────────────────────────────────────────
start "DTx Frontend — Expo" cmd /k "cd /d "%ROOT%\frontend" && echo. && echo  Expo starting... && echo  Press w to open in browser && echo  Scan QR code to open in Expo Go on your phone && echo. && npx expo start"

echo.
echo Both servers are starting in separate windows.
echo.
echo  Next steps:
echo  1. Wait ~5 seconds for both servers to initialise
echo  2. Press 'w' in the Expo window to open in your browser
echo  3. OR scan the QR code with the Expo Go app on your phone
echo.
pause
