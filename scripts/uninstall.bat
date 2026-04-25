@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   JARVIS-CC 제거
echo ============================================
echo.

echo [1/2] 자동 시작 해제...
python -m jarvis_cc.startup unregister

echo [2/2] 바탕화면 바로가기 삭제...
del "%USERPROFILE%\Desktop\JARVIS-CC.lnk" 2>nul
del "%USERPROFILE%\바탕 화면\JARVIS-CC.lnk" 2>nul

echo.
echo 제거 완료. pip 패키지는 수동 삭제하세요:
echo   pip uninstall pvporcupine pvrecorder edge-tts pyttsx3 pygame pynput pystray
echo.
pause
