"""JARVIS-CC 전체 설정 관리.

참조: clarvis src/config.ts (XDG TOML loader), claude-speak CLI args.
"""

import sys
import os
from pathlib import Path
from dataclasses import dataclass, field

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.toml"
USER_CONFIG_DIR = Path.home() / ".jarvis-cc"


@dataclass
class PorcupineConfig:
    access_key: str = ""
    keyword: str = "jarvis"
    sensitivity: float = 0.5
    device_index: int = -1


@dataclass
class TTSConfig:
    voice: str = "ko-KR-InJoonNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    fallback: str = "sapi"
    num_workers: int = 2
    queue_size: int = 50


@dataclass
class PersonaConfig:
    mode: str = "normal"        # brief / normal / full / bypass
    style: str = "butler"       # butler / casual / professional
    owner_name: str = "박대표님"


@dataclass
class MonitorConfig:
    debounce_ms: int = 2000
    poll_interval: float = 0.5
    max_spoken_ids: int = 2000
    claude_projects_dir: str = str(Path.home() / ".claude" / "projects")


@dataclass
class HUDConfig:
    enabled: bool = True
    opacity: float = 0.9
    width: int = 320
    height: int = 400
    theme_bg: str = "#0D1117"
    theme_accent: str = "#00B4FF"
    theme_text: str = "#E6EDF3"


@dataclass
class SoundConfig:
    enabled: bool = True
    volume: float = 0.7


@dataclass
class HotkeyConfig:
    hotkey: str = "<cmd>+j"


@dataclass
class WebUIConfig:
    port: int = 8910
    host: str = "127.0.0.1"


@dataclass
class JarvisConfig:
    porcupine: PorcupineConfig = field(default_factory=PorcupineConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    persona: PersonaConfig = field(default_factory=PersonaConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    hud: HUDConfig = field(default_factory=HUDConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    web_ui: WebUIConfig = field(default_factory=WebUIConfig)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "JarvisConfig":
        """TOML 파일에서 설정 로드. 없으면 기본값 사용."""
        config = cls()

        # 우선순위: 인자 > 사용자 디렉토리 > 프로젝트 기본
        candidates = []
        if path:
            candidates.append(Path(path))
        candidates.append(USER_CONFIG_DIR / "config.toml")
        candidates.append(DEFAULT_CONFIG_PATH)

        for candidate in candidates:
            if candidate.exists():
                config._load_from_toml(candidate)
                break

        # 환경변수 오버라이드
        config._load_from_env()
        return config

    def _load_from_toml(self, path: Path) -> None:
        if tomllib is None:
            return
        with open(path, "rb") as f:
            data = tomllib.load(f)

        section_map = {
            "porcupine": self.porcupine,
            "tts": self.tts,
            "persona": self.persona,
            "monitor": self.monitor,
            "hud": self.hud,
            "sound": self.sound,
            "hotkey": self.hotkey,
            "web_ui": self.web_ui,
        }
        for section_name, section_obj in section_map.items():
            if section_name in data:
                for key, value in data[section_name].items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)

    def _load_from_env(self) -> None:
        """환경변수 오버라이드: JARVIS_PORCUPINE_ACCESS_KEY 등."""
        env_key = os.environ.get("JARVIS_PORCUPINE_ACCESS_KEY")
        if env_key:
            self.porcupine.access_key = env_key

        env_voice = os.environ.get("JARVIS_TTS_VOICE")
        if env_voice:
            self.tts.voice = env_voice

        env_mode = os.environ.get("JARVIS_PERSONA_MODE")
        if env_mode and env_mode in ("brief", "normal", "full", "bypass"):
            self.persona.mode = env_mode

    def save(self, path: str | Path | None = None) -> None:
        """설정을 TOML 파일로 저장."""
        target = Path(path) if path else USER_CONFIG_DIR / "config.toml"
        target.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        section_map = {
            "porcupine": self.porcupine,
            "tts": self.tts,
            "persona": self.persona,
            "monitor": self.monitor,
            "hud": self.hud,
            "sound": self.sound,
            "hotkey": self.hotkey,
            "web_ui": self.web_ui,
        }
        for section_name, section_obj in section_map.items():
            lines.append(f"\n[{section_name}]")
            for key, value in section_obj.__dict__.items():
                if isinstance(value, str):
                    # TOML: 백슬래시 이스케이프 또는 리터럴 문자열 사용
                    escaped = value.replace("\\", "\\\\")
                    lines.append(f'{key} = "{escaped}"')
                elif isinstance(value, bool):
                    lines.append(f"{key} = {'true' if value else 'false'}")
                elif isinstance(value, (int, float)):
                    lines.append(f"{key} = {value}")

        target.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    cfg = JarvisConfig.load()
    print(f"[config] Wake keyword: {cfg.porcupine.keyword}")
    print(f"[config] TTS voice: {cfg.tts.voice}")
    print(f"[config] Persona mode: {cfg.persona.mode}")
    print(f"[config] Owner: {cfg.persona.owner_name}")
    print(f"[config] Web UI port: {cfg.web_ui.port}")
    print("[config] OK")
