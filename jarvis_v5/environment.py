"""DAVIS 업무환경 접속 정보 관리 — 암호화 저장 + 자동 로그인.

파일: ~/.jarvis-cc/environment.yaml (Fernet 암호화)
키: ~/.jarvis-cc/environment.key (마스터 키, 600 권한)
"""

import json
import logging
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("davis.env")

ENV_DIR = Path.home() / ".jarvis-cc"
ENV_DIR.mkdir(parents=True, exist_ok=True)
ENV_YAML_PATH = ENV_DIR / "environment.yaml"
ENV_ENCRYPTED_PATH = ENV_DIR / "environment.yaml.enc"
ENV_KEY_PATH = ENV_DIR / "environment.key"


def _get_or_create_key() -> bytes:
    """Fernet 마스터 키 로드/생성."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        logger.warning("cryptography not installed")
        return b""

    if ENV_KEY_PATH.exists():
        return ENV_KEY_PATH.read_bytes()
    key = Fernet.generate_key()
    ENV_KEY_PATH.write_bytes(key)
    try:
        os.chmod(ENV_KEY_PATH, 0o600)
    except Exception:
        pass
    logger.info("Encryption key generated")
    return key


# ─── 환경 정보 수집 ────────────────────────────────────────────────────

def scan_system() -> dict:
    """현재 PC의 개발 환경 스캔."""
    info = {
        "system": {
            "os": platform.system(),
            "version": platform.version(),
            "release": platform.release(),
            "hostname": socket.gethostname(),
            "user": os.environ.get("USERNAME") or os.environ.get("USER", ""),
        },
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
        },
        "tools": {},
        "network": {},
    }

    # 개발 도구 버전 확인
    tools_check = {
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "git": ["git", "--version"],
        "ffmpeg": ["ffmpeg", "-version"],
    }
    for name, cmd in tools_check.items():
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3,
                shell=(sys.platform == "win32"),
            )
            if result.returncode == 0:
                info["tools"][name] = result.stdout.strip().splitlines()[0][:80]
        except Exception:
            pass

    # Tailscale
    try:
        result = subprocess.run(
            ["tailscale", "status"],
            capture_output=True, text=True, timeout=3,
            shell=(sys.platform == "win32"),
        )
        if result.returncode == 0:
            info["network"]["tailscale"] = "connected"
    except Exception:
        info["network"]["tailscale"] = "not available"

    # Claude CLI 확인
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=3,
            shell=(sys.platform == "win32"),
        )
        if result.returncode == 0:
            info["tools"]["claude"] = result.stdout.strip()[:80]
    except Exception:
        pass

    return info


# ─── 암호화 저장/로드 ───────────────────────────────────────────────────

def save_environment(data: dict):
    """환경 정보 암호화 저장."""
    try:
        from cryptography.fernet import Fernet
        import yaml

        yaml_str = yaml.safe_dump(data, allow_unicode=True, default_flow_style=False)
        key = _get_or_create_key()
        if not key:
            # 암호화 없이 일반 저장 (경고)
            ENV_YAML_PATH.write_text(yaml_str, encoding="utf-8")
            logger.warning("Saved WITHOUT encryption")
            return

        f = Fernet(key)
        encrypted = f.encrypt(yaml_str.encode("utf-8"))
        ENV_ENCRYPTED_PATH.write_bytes(encrypted)
        try:
            os.chmod(ENV_ENCRYPTED_PATH, 0o600)
        except Exception:
            pass
        logger.info(f"Environment saved (encrypted): {ENV_ENCRYPTED_PATH}")
    except Exception as e:
        logger.error(f"Save error: {e}")


def load_environment() -> dict:
    """환경 정보 로드 (복호화)."""
    try:
        from cryptography.fernet import Fernet
        import yaml

        if ENV_ENCRYPTED_PATH.exists():
            key = _get_or_create_key()
            if key:
                f = Fernet(key)
                data = f.decrypt(ENV_ENCRYPTED_PATH.read_bytes())
                return yaml.safe_load(data.decode("utf-8")) or {}

        if ENV_YAML_PATH.exists():
            return yaml.safe_load(ENV_YAML_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.error(f"Load error: {e}")
    return {}


def _mask_sensitive(value: str) -> str:
    """민감 정보 마스킹 (응답용)."""
    if not value or len(value) < 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


# ─── 공개 도구 함수 ────────────────────────────────────────────────────

def get_env_info(key: Optional[str] = None, safe: bool = True) -> str:
    """환경 정보 조회 (민감 정보 마스킹).

    Args:
        key: 조회할 키 경로 (예: 'system.hostname'). None이면 전체 요약
        safe: True면 민감 필드 마스킹
    """
    data = load_environment()
    if not data:
        return "환경 정보가 아직 설정되지 않았습니다. davis_env_init으로 초기화하세요."

    if not key:
        # 전체 요약
        sys_info = data.get("system", {})
        tools = data.get("tools", {})
        lines = [
            f"OS: {sys_info.get('os', '?')} ({sys_info.get('hostname', '?')})",
            f"Python: {data.get('python', {}).get('version', '?')}",
            f"Tools: {', '.join(tools.keys()) if tools else '없음'}",
        ]
        credentials = data.get("credentials", {})
        if credentials:
            lines.append(f"등록된 자격증명: {', '.join(credentials.keys())}")
        return "\n".join(lines)

    # 특정 키 조회
    parts = key.split(".")
    value = data
    for p in parts:
        if isinstance(value, dict):
            value = value.get(p)
        else:
            return f"키 없음: {key}"
        if value is None:
            return f"키 없음: {key}"

    # 민감 정보 마스킹
    if safe and isinstance(value, str):
        if any(s in key.lower() for s in ["password", "pwd", "token", "key", "secret", "credential"]):
            return _mask_sensitive(value)

    return str(value)


def davis_env_init() -> str:
    """환경 정보 초기 스캔 + 저장."""
    try:
        scanned = scan_system()
        existing = load_environment()
        # 기존 credentials 유지, system/tools만 갱신
        merged = {
            **existing,
            "system": scanned["system"],
            "python": scanned["python"],
            "tools": scanned["tools"],
            "network": scanned["network"],
        }
        save_environment(merged)
        return (
            f"환경 스캔 완료. "
            f"OS={scanned['system']['os']}, "
            f"도구={len(scanned['tools'])}개 감지"
        )
    except Exception as e:
        return f"환경 초기화 실패: {e}"


def store_credential(service: str, username: str, password: str, url: str = "") -> str:
    """서비스 자격증명 저장 (암호화)."""
    try:
        data = load_environment()
        if "credentials" not in data:
            data["credentials"] = {}
        data["credentials"][service] = {
            "username": username,
            "password": password,
            "url": url,
        }
        save_environment(data)
        return f"{service} 자격증명 저장 완료 (암호화)"
    except Exception as e:
        return f"저장 실패: {e}"


# ─── 도구 스키마 ───────────────────────────────────────────────────────

ENV_TOOLS_SCHEMA = [
    {
        "name": "get_env_info",
        "description": "이 PC의 개발 환경 정보를 조회합니다 (OS, Python, 도구, 네트워크, 등록된 서비스).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "조회할 키 (예: 'system.hostname', 'tools.node'). 비우면 전체 요약."
                }
            }
        }
    },
    {
        "name": "env_init",
        "description": "이 PC의 개발 환경을 스캔하여 저장합니다. 최초 1회 실행.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "store_credential",
        "description": "서비스 자격증명을 암호화 저장합니다 (ERP, Decohub, Taskworld 등).",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "서비스명 (예: 'ERP', 'Taskworld')"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "url": {"type": "string", "description": "접속 URL (선택)"}
            },
            "required": ["service", "username", "password"]
        }
    },
]


def execute_env_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "get_env_info":
            return get_env_info(tool_input.get("key"))
        elif tool_name == "env_init":
            return davis_env_init()
        elif tool_name == "store_credential":
            return store_credential(
                tool_input["service"],
                tool_input["username"],
                tool_input["password"],
                tool_input.get("url", ""),
            )
        return f"ERROR: 알 수 없는 도구 {tool_name}"
    except Exception as e:
        return f"ERROR: {e}"


def is_env_tool(name: str) -> bool:
    return name in {"get_env_info", "env_init", "store_credential"}


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO)

    print("=== 환경 스캔 ===")
    print(davis_env_init())
    print()
    print("=== 환경 조회 ===")
    print(get_env_info())
