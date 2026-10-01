@echo off
REM Script to launch Frontend and Backend in terminal tabs (using Windows Terminal `wt` if available)

wt -w 0 nt --title "Backend" cmd /k "cd /d "%~dp0backend" && uvicorn app.main:app --reload --port 8000" 2>nul
if %errorlevel% neq 0 (
    echo [Info] Windows Terminal not found. Opening standard terminal windows instead.
    start "Backend" cmd /k "cd /d "%~dp0backend" && uvicorn app.main:app --reload --port 8000"
    start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
) else (
    wt -w 0 nt --title "Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
)
