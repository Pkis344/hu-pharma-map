@echo off
REM ============================================================
REM  Logistics and Sales mapping overview - Dashboard V5 launcher
REM  Starts a local web server at the project root so the dashboard
REM  can read the Excel in "Dashboard Input", then opens it in the
REM  browser once the server is actually accepting connections.
REM ============================================================

setlocal
set PORT=8767
REM Cache-buster (?v=NNNN, new each launch) so the browser always fetches the latest
REM index.html instead of showing a stale cached copy.
set URL=http://localhost:%PORT%/Dashboards/Dashboard%%20V5/index.html?v=%RANDOM%%RANDOM%

REM Go to the project root (two levels up from this .bat: ...\HU Pharma Map)
cd /d "%~dp0..\.."

REM If a server is already listening on this port, just open the browser and quit.
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo A local server is already running on port %PORT%. Opening the dashboard...
  start "" "%URL%"
  goto :end
)

REM Pick a real Python. Prefer the "py" launcher; fall back to "python".
REM Test with --version so a non-working command is skipped.
set "PYCMD="
py -3 --version >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD ( python --version >nul 2>&1 && set "PYCMD=python" )
if not defined PYCMD (
  echo.
  echo ERROR: Python 3 was not found. Install it from https://python.org
  echo ^(tick "Add Python to PATH" during setup^), or open this address manually:
  echo   %URL%
  echo.
  pause
  goto :end
)

echo Starting local server on http://localhost:%PORT% ...
echo (Leave this window open while using the dashboard. Close it when done.)
echo.

REM Open the browser ONLY after the server is accepting connections
REM (polls the port for up to ~20s) so you never hit "connection refused".
start "" powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 40;$i++){ try{ $c=New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',%PORT%); $c.Close(); Start-Process '%URL%'; break } catch { Start-Sleep -Milliseconds 500 } }"

REM Serve the project root. This blocks; closing this window stops the server.
%PYCMD% -m http.server %PORT%

REM If we get here the server stopped or failed to start.
echo.
echo The local server has stopped. If the page said "connection refused",
echo check the messages above, or open this address manually:
echo   %URL%
echo.
pause

:end
endlocal
