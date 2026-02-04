@echo off
chcp 65001 >nul
echo ========================================
echo   Auto_All_System 打包脚本
echo ========================================
echo.

REM 检查 PyInstaller 是否安装
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [安装] PyInstaller 未安装，正在安装...
    pip install pyinstaller
)

echo [打包] 开始打包...
echo.

REM 使用 spec 文件打包
pyinstaller --clean Auto_All_System.spec

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包完成！
echo   输出目录: dist\Auto_All_System.exe
echo ========================================
echo.

REM 复制数据库文件（如果存在）
if exist "data\accounts.db" (
    echo [复制] 复制数据库文件...
    if not exist "dist\data" mkdir "dist\data"
    copy "data\accounts.db" "dist\data\" >nul
)

pause
