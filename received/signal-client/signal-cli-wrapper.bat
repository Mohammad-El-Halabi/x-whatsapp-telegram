@echo off
setlocal EnableExtensions

set "APP_ROOT=%~dp0"
set "JAVA_EXE="

if defined JAVA_HOME if exist "%JAVA_HOME%\bin\java.exe" set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
if not defined JAVA_EXE if exist "%APP_ROOT%runtime\java\bin\java.exe" set "JAVA_EXE=%APP_ROOT%runtime\java\bin\java.exe"
if not defined JAVA_EXE for /d %%D in ("%APP_ROOT%runtime\java\*") do if exist "%%~fD\bin\java.exe" set "JAVA_EXE=%%~fD\bin\java.exe"

if not defined JAVA_EXE (
    echo Java 25 runtime not found. Run prepare-runtime.ps1 first. 1>&2
    exit /b 1
)

if not exist "%APP_ROOT%signal-cli\lib\signal-cli-*.jar" (
    echo signal-cli runtime not found. Run prepare-runtime.ps1 first. 1>&2
    exit /b 1
)

rem A wildcard classpath avoids Windows' command-line length limit in the
rem generated upstream launcher when this project is inside a long path.
"%JAVA_EXE%" --enable-native-access=ALL-UNNAMED -classpath "%APP_ROOT%signal-cli\lib\*" org.asamk.signal.Main %*
exit /b %ERRORLEVEL%
