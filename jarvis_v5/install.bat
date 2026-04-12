@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   JARVIS-CC v5 설치
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    pause
    exit /b 1
)

echo [1/3] 의존성 설치...
pip install -r jarvis_v5/requirements.txt
echo.

echo [2/3] .env 파일 확인...
if not exist .env (
    echo [WARNING] .env 파일이 없습니다.
    echo   .env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요.
)
echo.

echo [3/3] 설치 완료!
echo.
echo 실행: python jarvis_v5/jarvis.py
echo.
pause
