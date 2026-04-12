@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   JARVIS-CC v4 (LiveKit) 시작
echo ============================================
echo.

:: 환경변수 설정
set LIVEKIT_URL=ws://localhost:7880
set LIVEKIT_API_KEY=devkey
set LIVEKIT_API_SECRET=secret

:: Anthropic API Key 확인
if "%ANTHROPIC_API_KEY%"=="" (
    echo [ERROR] ANTHROPIC_API_KEY가 설정되지 않았습니다.
    echo   set ANTHROPIC_API_KEY=your_key
    pause
    exit /b 1
)

:: OpenAI API Key 확인 (STT/TTS용)
if "%OPENAI_API_KEY%"=="" (
    echo [WARNING] OPENAI_API_KEY가 없으면 STT/TTS가 작동하지 않습니다.
    echo   set OPENAI_API_KEY=your_key
)

echo.
echo [1/2] LiveKit Server 시작...
start /B "LiveKit Server" "%~dp0livekit-server\livekit-server.exe" --dev --bind 0.0.0.0

timeout /t 3 >nul

echo [2/2] JARVIS Agent 시작...
echo.
echo   접속: https://agents-playground.livekit.io
echo   LiveKit URL: ws://localhost:7880
echo.

python jarvis_agent.py dev
