@echo off
title SEUL-JJEOCK APK BUILDER
cd /d "%~dp0"

echo ===================================================
echo   [SEUL-JJEOCK] Building Android APK...
echo ===================================================
echo.

if "%JAVA_HOME%"=="" (
    if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Eclipse Adoptium\jdk-17.0.20.101-hotspot" (
        set "JAVA_HOME=C:\Users\%USERNAME%\AppData\Local\Programs\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
    )
)
if defined JAVA_HOME (
    set "PATH=%JAVA_HOME%\bin;%PATH%"
)

if "%ANDROID_HOME%"=="" (
    if exist "%LOCALAPPDATA%\Android\Sdk" (
        set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
        set "ANDROID_SDK_ROOT=%LOCALAPPDATA%\Android\Sdk"
    )
)

echo [*] Step 1/4: Building Frontend Bundle (Vite)...
cd /d "%~dp0frontend"
call npm.cmd run build
if %errorlevel% neq 0 (
    echo [!] Frontend build failed!
    pause
    exit /b %errorlevel%
)

echo.
echo [*] Step 2/4: Syncing Capacitor Android...
call npx.cmd cap sync android
if %errorlevel% neq 0 (
    echo [!] Capacitor sync failed!
    pause
    exit /b %errorlevel%
)

echo.
echo [*] Step 3/4: Packaging APK with Gradle assembleDebug (30~60s)...
cd /d "%~dp0frontend\android"
call gradlew.bat assembleDebug
if %errorlevel% neq 0 (
    echo [!] Gradle APK packaging failed!
    pause
    exit /b %errorlevel%
)

echo.
echo [*] Step 4/4: Copying APK and creating ZIP archive...
cd /d "%~dp0"
copy /y "frontend\android\app\build\outputs\apk\debug\app-debug.apk" "슬쩍_debug.apk" >nul

powershell -Command "Compress-Archive -Path '슬쩍_debug.apk' -DestinationPath '슬쩍_debug.zip' -Force"

echo.
echo ===================================================
echo   [SUCCESS] APK build completed successfully!
echo ===================================================
echo   1. APK File (For Android Phone Install):
echo      - %~dp0슬쩍_debug.apk
echo.
echo   2. ZIP File (For KakaoTalk / Messenger Sharing):
echo      - %~dp0슬쩍_debug.zip
echo ===================================================
echo.

explorer.exe /select,"%~dp0슬쩍_debug.apk"
pause
