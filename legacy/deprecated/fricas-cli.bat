@echo off
setlocal enabledelayedexpansion

set "FRICAS_PATH=C:\Users\FoadS\scoop\apps\fricas\1.3.12\bin\FRICASsys.exe"

if "%1"=="" goto :usage
if /i "%1"=="version" goto :version
if /i "%1"=="help" goto :help
if /i "%1"=="eval" goto :eval
if /i "%1"=="interactive" goto :interactive

:usage
echo FriCAS CLI Wrapper
echo Usage: fricas-cli ^<command^> [arguments]
echo.
echo Commands:
echo   version     - Show FriCAS version
echo   help        - Show available commands
echo   eval ^<expr^> - Evaluate expression
echo   interactive - Start FriCAS
goto :eof

:version
echo )quit | "%FRICAS_PATH%" --version 2>nul | findstr /i "Version.*FriCAS"
goto :eof

:help
echo )help > temp_fricas_cmd.txt
echo )quit >> temp_fricas_cmd.txt
"%FRICAS_PATH%" --non-interactive < temp_fricas_cmd.txt 2>nul
del temp_fricas_cmd.txt
goto :eof

:eval
shift
set "EXPR=%*"
echo %EXPR% > temp_fricas_cmd.txt
echo )quit >> temp_fricas_cmd.txt
"%FRICAS_PATH%" --non-interactive < temp_fricas_cmd.txt 2>nul
del temp_fricas_cmd.txt
goto :eof

:interactive
"%FRICAS_PATH%"
goto :eof
