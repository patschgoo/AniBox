@echo off
rem AniBox Library Check: double-click to run. Extra options can be passed on the command line.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m anibox_check %*
) else (
  python -m anibox_check %*
)
echo.
pause
