"""DAVIS 자가 진화 도구 — 자기 소스코드 읽기/수정/테스트/재시작.

안전 메커니즘:
- 수정 전 자동 백업 (.bak)
- 구문 검사 (ast.parse)
- 실패 시 자동 롤백
"""

import ast
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# DAVIS 소스 디렉토리
DAVIS_DIR = Path(__file__).parent
BACKUP_DIR = DAVIS_DIR / ".backups"
BACKUP_DIR.mkdir(exist_ok=True)

# 허용된 파일만 수정 가능 (보안)
ALLOWED_FILES = {
    "jarvis.py",
    "self_tools.py",
}


# ─── 도구 스키마 (Claude API용) ──────────────────────────────────────────

_BASE_TOOLS = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 3,
    },
    {
        "name": "read_source",
        "description": "DAVIS 자기 자신의 소스코드 파일을 읽습니다. jarvis.py, self_tools.py만 허용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "읽을 파일명 (jarvis.py 또는 self_tools.py)"
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "edit_source",
        "description": (
            "DAVIS 자기 자신의 소스코드를 수정합니다. "
            "old_text를 new_text로 정확히 치환합니다. "
            "자동으로 백업되며, 구문 에러 시 롤백됩니다."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "수정할 파일명"},
                "old_text": {"type": "string", "description": "교체할 기존 코드 (정확히 일치해야 함)"},
                "new_text": {"type": "string", "description": "새로운 코드"},
                "reason": {"type": "string", "description": "수정 이유 (한 문장)"}
            },
            "required": ["filename", "old_text", "new_text", "reason"]
        }
    },
    {
        "name": "install_package",
        "description": "pip으로 Python 패키지를 설치합니다. 새 기능 구현에 필요한 라이브러리 추가.",
        "input_schema": {
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "패키지명 (예: 'requests')"}
            },
            "required": ["package"]
        }
    },
    {
        "name": "restart_davis",
        "description": "DAVIS를 재시작하여 변경사항을 적용합니다. 코드 수정 후 호출하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "재시작 이유"}
            },
            "required": ["reason"]
        }
    },
    {
        "name": "rollback",
        "description": "마지막 수정을 취소하고 이전 백업으로 복원합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "롤백할 파일명"}
            },
            "required": ["filename"]
        }
    },
]


def _build_tools_schema():
    """베이스 도구 + Google + 환경 도구 병합."""
    tools = list(_BASE_TOOLS)
    try:
        from google_tools import GOOGLE_TOOLS_SCHEMA
        tools.extend(GOOGLE_TOOLS_SCHEMA)
    except ImportError:
        pass
    try:
        from environment import ENV_TOOLS_SCHEMA
        tools.extend(ENV_TOOLS_SCHEMA)
    except ImportError:
        pass
    return tools


TOOLS_SCHEMA = _build_tools_schema()


# ─── 도구 실행 함수 ──────────────────────────────────────────────────────

def _validate_filename(filename: str) -> Path | None:
    """파일명 검증 및 경로 반환."""
    if filename not in ALLOWED_FILES:
        return None
    path = DAVIS_DIR / filename
    if not path.exists():
        return None
    return path


def _backup_file(path: Path) -> Path:
    """파일 백업 (.backups/파일명_타임스탬프)."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{path.stem}_{ts}{path.suffix}"
    shutil.copy2(path, backup_path)
    return backup_path


def _check_syntax(path: Path) -> tuple[bool, str]:
    """Python 구문 검사."""
    try:
        code = path.read_text(encoding="utf-8")
        ast.parse(code)
        return True, "OK"
    except SyntaxError as e:
        return False, f"구문 에러: {e.msg} (line {e.lineno})"
    except Exception as e:
        return False, f"검사 실패: {e}"


def read_source(filename: str) -> str:
    """소스코드 읽기."""
    path = _validate_filename(filename)
    if not path:
        return f"ERROR: {filename}은 읽을 수 없습니다. 허용된 파일: {ALLOWED_FILES}"

    content = path.read_text(encoding="utf-8")
    # 너무 길면 요약
    if len(content) > 8000:
        return f"{content[:8000]}\n\n...(생략됨. 전체 {len(content)}자)"
    return content


def edit_source(filename: str, old_text: str, new_text: str, reason: str) -> str:
    """소스코드 수정 (백업 + 구문 검사)."""
    path = _validate_filename(filename)
    if not path:
        return f"ERROR: {filename}은 수정할 수 없습니다."

    try:
        # 백업
        backup = _backup_file(path)

        # 읽기
        content = path.read_text(encoding="utf-8")

        # 치환 가능 여부 확인
        if old_text not in content:
            return f"ERROR: old_text를 찾을 수 없습니다. 파일을 먼저 read_source로 읽어보세요."

        count = content.count(old_text)
        if count > 1:
            return f"ERROR: old_text가 {count}번 발견됨. 더 구체적인 문맥 포함 필요."

        # 치환
        new_content = content.replace(old_text, new_text)
        path.write_text(new_content, encoding="utf-8")

        # 구문 검사
        ok, msg = _check_syntax(path)
        if not ok:
            # 롤백
            shutil.copy2(backup, path)
            return f"ERROR: 구문 에러로 롤백됨. {msg}"

        return f"OK: {filename} 수정 완료. 이유: {reason}. 백업: {backup.name}. 재시작 필요."

    except Exception as e:
        return f"ERROR: {e}"


def install_package(package: str) -> str:
    """pip install."""
    # 위험한 패키지 차단
    if any(danger in package.lower() for danger in ["os", "sys", "subprocess", "eval"]):
        return f"ERROR: 위험한 패키지명 거부됨: {package}"

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", package],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            return f"OK: {package} 설치 완료"
        return f"ERROR: {result.stderr[-300:]}"
    except subprocess.TimeoutExpired:
        return "ERROR: 설치 타임아웃 (120초)"
    except Exception as e:
        return f"ERROR: {e}"


def restart_davis(reason: str) -> str:
    """DAVIS 재시작 (새 프로세스 시작 후 자신 종료)."""
    import threading

    def _delayed_restart():
        time.sleep(2)
        try:
            # 새 인스턴스 시작
            subprocess.Popen(
                [sys.executable, str(DAVIS_DIR / "jarvis.py")],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            time.sleep(1)
            # 자기 자신 종료
            os._exit(0)
        except Exception as e:
            print(f"Restart error: {e}")

    threading.Thread(target=_delayed_restart, daemon=True).start()
    return f"OK: 3초 후 재시작합니다. 이유: {reason}"


def rollback(filename: str) -> str:
    """가장 최근 백업으로 롤백."""
    path = _validate_filename(filename)
    if not path:
        return f"ERROR: {filename} 롤백 불가"

    # 가장 최근 백업 찾기
    backups = sorted(
        BACKUP_DIR.glob(f"{path.stem}_*{path.suffix}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        return f"ERROR: {filename}의 백업 없음"

    latest = backups[0]
    shutil.copy2(latest, path)

    # 구문 검사
    ok, msg = _check_syntax(path)
    return f"OK: {filename} 롤백 완료. 복원: {latest.name}. 구문: {msg}"


# ─── 도구 실행 디스패처 ──────────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """도구 이름으로 실행 디스패치."""
    try:
        if tool_name == "read_source":
            return read_source(tool_input.get("filename", ""))
        elif tool_name == "edit_source":
            return edit_source(
                tool_input.get("filename", ""),
                tool_input.get("old_text", ""),
                tool_input.get("new_text", ""),
                tool_input.get("reason", ""),
            )
        elif tool_name == "install_package":
            return install_package(tool_input.get("package", ""))
        elif tool_name == "restart_davis":
            return restart_davis(tool_input.get("reason", ""))
        elif tool_name == "rollback":
            return rollback(tool_input.get("filename", ""))

        # Google 도구 위임
        try:
            from google_tools import is_google_tool, execute_google_tool
            if is_google_tool(tool_name):
                return execute_google_tool(tool_name, tool_input)
        except ImportError:
            pass

        # 환경 정보 도구 위임
        try:
            from environment import is_env_tool, execute_env_tool
            if is_env_tool(tool_name):
                return execute_env_tool(tool_name, tool_input)
        except ImportError:
            pass

        return f"ERROR: 알 수 없는 도구 {tool_name}"
    except Exception as e:
        return f"ERROR: 도구 실행 실패 - {e}"


if __name__ == "__main__":
    # 테스트
    print("=== Self-Tools 테스트 ===")
    print(f"DAVIS_DIR: {DAVIS_DIR}")
    print(f"허용 파일: {ALLOWED_FILES}")
    print()
    result = read_source("jarvis.py")
    print(f"read_source('jarvis.py'): {len(result)}자 읽음")
