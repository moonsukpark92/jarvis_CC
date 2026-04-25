@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   JARVIS-CC PyInstaller EXE 빌드
echo ============================================
echo.

pip install pyinstaller >nul 2>&1

pyinstaller --onefile --noconsole ^
  --name JARVIS-CC ^
  --add-data "jarvis_cc/assets;jarvis_cc/assets" ^
  --add-data "jarvis_cc/web_ui/static;jarvis_cc/web_ui/static" ^
  --add-data "jarvis_cc/config.toml;jarvis_cc" ^
  --hidden-import edge_tts ^
  --hidden-import pyttsx3 ^
  --hidden-import pvporcupine ^
  --hidden-import pvrecorder ^
  --hidden-import pynput ^
  --hidden-import pystray ^
  --icon jarvis_cc/assets/icon.ico ^
  jarvis_cc/main.py

echo.
if exist dist\JARVIS-CC.exe (
    echo 빌드 성공: dist\JARVIS-CC.exe
) else (
    echo 빌드 실패. 로그를 확인하세요.
)
pause
