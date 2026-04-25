"""Windows 자동 시작 — Task Scheduler (schtasks) 등록/해제.

부팅(로그온) 시 JARVIS-CC 자동 실행.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

TASK_NAME = "JARVIS-CC"


def _get_exe_path() -> str:
    """실행 파일 경로 결정."""
    # PyInstaller EXE인 경우
    if getattr(sys, "frozen", False):
        return sys.executable

    # Python 스크립트인 경우
    main_py = Path(__file__).parent / "main.py"
    return f'"{sys.executable}" "{main_py}"'


def register_autostart(exe_path: str | None = None, delay: str = "0:30") -> bool:
    """Task Scheduler에 자동 시작 등록.

    Args:
        exe_path: 실행할 경로 (None이면 자동 감지)
        delay: 로그온 후 지연 시간 (기본 30초)
    """
    if exe_path is None:
        exe_path = _get_exe_path()

    cmd = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", exe_path,
        "/sc", "ONLOGON",
        "/delay", delay,
        "/f",               # 기존 작업 덮어쓰기
        "/rl", "LIMITED",   # 관리자 권한 불필요
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode == 0:
            logger.info(f"Autostart registered: {TASK_NAME}")
            print(f"[startup] JARVIS-CC 자동 시작 등록 완료 (로그온 후 {delay} 지연)")
            return True
        else:
            logger.error(f"schtasks create failed: {result.stderr}")
            print(f"[startup] 등록 실패: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"Autostart register error: {e}")
        return False


def unregister_autostart() -> bool:
    """자동 시작 해제."""
    try:
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode == 0:
            logger.info(f"Autostart unregistered: {TASK_NAME}")
            print("[startup] JARVIS-CC 자동 시작 해제 완료")
            return True
        else:
            logger.error(f"schtasks delete failed: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Autostart unregister error: {e}")
        return False


def is_registered() -> bool:
    """자동 시작 등록 여부 확인."""
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", TASK_NAME],
            capture_output=True, text=True, encoding="utf-8",
        )
        return result.returncode == 0
    except Exception:
        return False


def create_desktop_shortcut() -> bool:
    """바탕화면에 JARVIS-CC 바로가기 생성."""
    try:
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "바탕 화면"
        if not desktop.exists():
            logger.warning("Desktop folder not found")
            return False

        shortcut_path = desktop / "JARVIS-CC.lnk"
        exe_path = _get_exe_path()

        # PowerShell로 바로가기 생성
        ps_script = f'''
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut("{shortcut_path}")
$sc.TargetPath = "{sys.executable}"
$sc.Arguments = '"{Path(__file__).parent / "main.py"}"'
$sc.WorkingDirectory = "{Path(__file__).parent.parent}"
$sc.Description = "JARVIS-CC Voice Assistant"
$sc.Save()
'''
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=10,
        )
        logger.info(f"Desktop shortcut created: {shortcut_path}")
        print(f"[startup] 바탕화면 바로가기 생성: {shortcut_path}")
        return True

    except Exception as e:
        logger.error(f"Shortcut creation error: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    status = "등록됨" if is_registered() else "미등록"
    print(f"[startup] JARVIS-CC 자동 시작: {status}")
    print(f"[startup] 실행 경로: {_get_exe_path()}")
    print()
    print("사용법:")
    print("  python -m jarvis_cc.startup register   # 자동 시작 등록")
    print("  python -m jarvis_cc.startup unregister  # 자동 시작 해제")
    print("  python -m jarvis_cc.startup shortcut    # 바탕화면 바로가기")

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "register":
            register_autostart()
        elif cmd == "unregister":
            unregister_autostart()
        elif cmd == "shortcut":
            create_desktop_shortcut()
