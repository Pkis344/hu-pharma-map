@echo off
REM ============================================================
REM  Self-hosted OSRM for Dashboard V5 - Hungary road routing
REM
REM  First run: downloads the Hungary map extract and builds the
REM  routing graph - one-time, about 5-10 min. Every run after that
REM  starts the routing server on http://localhost:5000 in seconds.
REM
REM  Leave this window OPEN while using V5's live routing. Close it
REM  or press Ctrl+C to stop the server. V5 still works without it
REM  - it falls back to precomputed roads + straight-line estimates.
REM
REM  Requires Docker Desktop - free. See SETUP.md for the full guide.
REM ============================================================

setlocal
set IMAGE=ghcr.io/project-osrm/osrm-backend
set PBF=hungary-latest.osm.pbf
set OSRM=hungary-latest.osrm
set PBF_URL=https://download.geofabrik.de/europe/hungary-latest.osm.pbf

REM Shared data folder at the project root - reusable across dashboard versions
set DATA=%~dp0..\..\osrm-data
if not exist "%DATA%" mkdir "%DATA%"
cd /d "%DATA%"

REM --- Resolve the Docker CLI: prefer PATH, else the per-user Docker Desktop install ---
set "DOCKER=docker"
docker --version >nul 2>&1
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe" set "DOCKER=%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe"

"%DOCKER%" --version >nul 2>&1
if errorlevel 1 goto :nodocker

"%DOCKER%" info >nul 2>&1
if errorlevel 1 goto :noengine

REM --- Download the Hungary extract if we don't have it ---
if exist "%PBF%" goto :haveextract
echo Downloading the Hungary map extract - about 250 MB, one time...
curl -L -o "%PBF%" "%PBF_URL%"
if errorlevel 1 goto :dlfail
:haveextract

REM --- Build the routing graph once - marker file _built.ok means done ---
if exist "_built.ok" goto :serve
echo.
echo Building the routing graph. This is a ONE-TIME step, about 5-10 minutes...
echo   [1/3] extract
"%DOCKER%" run --rm -t -v "%CD%:/data" %IMAGE% osrm-extract -p /opt/car.lua /data/%PBF%
if errorlevel 1 goto :buildfail
echo   [2/3] partition
"%DOCKER%" run --rm -t -v "%CD%:/data" %IMAGE% osrm-partition /data/%OSRM%
if errorlevel 1 goto :buildfail
echo   [3/3] customize
"%DOCKER%" run --rm -t -v "%CD%:/data" %IMAGE% osrm-customize /data/%OSRM%
if errorlevel 1 goto :buildfail
> "_built.ok" echo built
echo Build complete.

:serve
echo.
echo Starting OSRM on http://localhost:5000
echo Leave this window open while using the dashboard. Close it to stop.
echo.
"%DOCKER%" rm -f osrm-hu >nul 2>&1
"%DOCKER%" run --rm -t -i --name osrm-hu -p 5000:5000 -v "%CD%:/data" %IMAGE% osrm-routed --algorithm mld /data/%OSRM%
echo.
echo OSRM server stopped.
goto :end

:nodocker
echo.
echo ERROR: Docker was not found.
echo Install Docker Desktop - free - from https://www.docker.com/products/docker-desktop/
echo then run this file again. See SETUP.md for step-by-step help.
echo.
pause
goto :end

:noengine
echo.
echo Docker is installed but the engine is not running.
echo Start Docker Desktop, wait until it says Engine running, then re-run this file.
echo.
pause
goto :end

:dlfail
echo.
echo ERROR: download failed. Check your internet connection and re-run.
echo Or download it manually from:
echo   %PBF_URL%
echo and save it into: %DATA%
echo.
pause
goto :end

:buildfail
echo.
echo ERROR: the build step failed. Scroll up for the Docker message.
echo A common cause is too little memory given to Docker Desktop
echo   - Settings, Resources - or a corrupt download - delete %PBF% and retry.
echo.
pause

:end
endlocal
