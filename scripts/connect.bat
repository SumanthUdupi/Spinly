@echo off
:: =============================================================================
::  connect.bat  —  Spinly Tester Connection  (Windows)
::
::  BEFORE running:
::    Ask the person running the server for their machine's IP address.
::    On Linux/WSL2: run  hostname -I | awk '{print $1}'
::    On Windows:    run  ipconfig  and look for "IPv4 Address"
::
::  USAGE — either:
::    Double-click this file and type the IP when asked
::    OR paste this directly into any CMD window:
::
::    ssh -L 8000:127.0.0.1:8000 -L 9000:127.0.0.1:9000 frappe@THEIR_IP
::    Password: Exponent@15mins
::
::  After connecting, open: http://127.0.0.1:8000
::  Login: Administrator  /  admin
::  POS  : http://127.0.0.1:8000/spinly-pos
:: =============================================================================

echo.
echo  =============================================
echo   Spinly  ^|  Tester Connection
echo  =============================================
echo.

set /p HOST_IP="  Enter the Spinly server IP address: "

echo.
echo  Connecting to %HOST_IP% ...
echo.
echo  When prompted, enter the password:
echo    Exponent@15mins
echo.
echo  Once connected, open your browser at:
echo    http://127.0.0.1:8000
echo.
echo  Frappe login
echo    Username : Administrator
echo    Password : admin
echo.
echo  POS: http://127.0.0.1:8000/spinly-pos
echo.
echo  Press Ctrl+C to disconnect.
echo  ---------------------------------------------
echo.

ssh -L 8000:127.0.0.1:8000 -L 9000:127.0.0.1:9000 frappe@%HOST_IP%

echo.
echo  Disconnected.
pause
