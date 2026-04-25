@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   JARVIS-CC v3.0 설치
echo ============================================
echo.

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    echo Python 3.12+ 설치 후 다시 시도하세요.
    pause
    exit /b 1
)

:: 의존성 설치
echo [1/4] 의존성 설치 중...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] 일부 패키지 설치 실패. 계속합니다...
)

:: 사운드 에셋 생성
echo [2/4] 사운드 에셋 생성 중...
python -c "from jarvis_cc.sound_fx import ensure_assets; ensure_assets()"

:: Task Scheduler 등록
echo [3/4] 자동 시작 등록 중...
python -m jarvis_cc.startup register

:: 바탕화면 바로가기
echo [4/4] 바탕화면 바로가기 생성 중...
python -m jarvis_cc.startup shortcut

echo.
echo ============================================
echo   설치 완료!
echo ============================================
echo.
echo 중요: Porcupine AccessKey를 설정하세요
echo   1. https://picovoice.ai/ 에서 무료 가입
echo   2. Console에서 AccessKey 발급
echo   3. config.toml 또는 환경변수에 설정:
echo      set JARVIS_PORCUPINE_ACCESS_KEY=your_key
echo.
echo 실행: python -m jarvis_cc.main
echo 설정: http://localhost:8910
echo.
pause
