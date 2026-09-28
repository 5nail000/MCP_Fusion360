@echo off
setlocal
set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
for %%I in ("%~dp0..") do set "FCA_ROOT=%%~fI"
if not exist "%UV_EXE%" (
    echo [%DATE% %TIME%] [ERROR] uv.exe не найден в %%USERPROFILE%%\.local\bin 1>&2
    exit /b 1
)
"%UV_EXE%" run --directory "%FCA_ROOT%" fusion-cad-ai %*
exit /b %ERRORLEVEL%
