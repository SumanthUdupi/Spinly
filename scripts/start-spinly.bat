@echo off
setlocal

:: =============================================================================
::  start-spinly.bat  —  Spinly Local Launcher  (Windows CMD)
::
::  Works on any Windows machine with WSL2 + Ubuntu + Spinly installed.
::  Double-click or run from CMD. Enter the password, browser opens automatically.
::
::  Password : Spinly@access
::  App URL  : http://localhost
::  Login    : Administrator / admin
:: =============================================================================

set CORRECT_PASS=Spinly@access
set APP_URL=http://localhost
set BENCH_DIR=/home/frappe/frappe-bench

:: ── Banner ────────────────────────────────────────────────────────────────────
echo.
echo  =============================================
echo   Spinly  ^|  Local Launcher
echo  =============================================
echo.

:: ── Password check ────────────────────────────────────────────────────────────
set /p "INPUT_PASS=  Enter password: "

if not "%INPUT_PASS%"=="%CORRECT_PASS%" (
    echo.
    echo  [!] Incorrect password. Access denied.
    echo.
    pause
    exit /b 1
)

echo.
echo  [OK] Access granted.
echo.

:: ── Find Ubuntu WSL distro (PowerShell to handle UTF-16 output) ───────────────
set WSL_DISTRO=
for /f "delims=" %%D in ('powershell -NoProfile -Command "((wsl --list --quiet) -replace [char]0,'' -replace [char]13,'').Trim() | Where-Object { $_ -match 'Ubuntu' } | Select-Object -First 1" 2^>nul') do (
    if not defined WSL_DISTRO set WSL_DISTRO=%%D
)

if not defined WSL_DISTRO (
    echo  [!] No Ubuntu WSL distro found.
    echo      Please install Ubuntu from the Microsoft Store.
    echo.
    pause
    exit /b 1
)

echo  Using WSL distro: %WSL_DISTRO%
echo.

:: ── Check if app is already responding ───────────────────────────────────────
echo  Checking if Spinly services are running...
wsl -d %WSL_DISTRO% -u root -- bash -c "curl -s --max-time 3 http://localhost/api/method/frappe.ping 2>/dev/null | grep -q pong"

if %errorlevel% EQU 0 (
    echo  [OK] Services already running.
    goto READY
)

:: ── Start WSL services ────────────────────────────────────────────────────────
echo  Starting services, please wait...
wsl -d %WSL_DISTRO% -u root -- bash -c "systemctl start mariadb 2>/dev/null; sleep 3; systemctl start supervisor 2>/dev/null; supervisorctl start all 2>/dev/null"

:: ── Wait for app to respond (max 60 s) ───────────────────────────────────────
echo  Waiting for app to be ready (up to 60 seconds)...
set /a TRIES=0

:WAIT_LOOP
set /a TRIES+=1
wsl -d %WSL_DISTRO% -u root -- bash -c "curl -s --max-time 3 http://localhost/api/method/frappe.ping 2>/dev/null | grep -q pong"

if %errorlevel% EQU 0 goto READY

if %TRIES% GEQ 30 (
    echo.
    echo  [!] Services did not start in time.
    echo      Make sure WSL2 Ubuntu is installed with Spinly set up.
    echo.
    pause
    exit /b 1
)

if %TRIES% EQU 10 echo  Still loading... (gunicorn preloading)
if %TRIES% EQU 20 echo  Almost ready...
timeout /t 2 /nobreak >nul
goto WAIT_LOOP

:: ── Open browser ─────────────────────────────────────────────────────────────
:READY
echo  [OK] Spinly is running.
echo.
echo  =============================================
echo   Opening : %APP_URL%
echo   Login   : Administrator / admin
echo  =============================================
echo.
start "" "%APP_URL%"

echo  Press any key to close this window.
pause >nul
endlocal
