"""DAVIS Google Workspace 도구 — Gmail, Drive, Calendar.

첫 사용 시 브라우저 OAuth 창이 열리고, 승인 후 토큰이 ~/.jarvis-cc/google_token.json에 저장됨.
이후 자동 사용.

필요 파일: ~/.jarvis-cc/google_credentials.json (OAuth 클라이언트)
  1. console.cloud.google.com 접속
  2. 프로젝트 생성 → OAuth 동의 화면 설정
  3. 사용자 인증 정보 → OAuth 클라이언트 ID (데스크톱 앱)
  4. JSON 다운로드 → google_credentials.json으로 저장
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("davis.google")

GOOGLE_DIR = Path.home() / ".jarvis-cc"
GOOGLE_DIR.mkdir(parents=True, exist_ok=True)
CREDENTIALS_PATH = GOOGLE_DIR / "google_credentials.json"
TOKEN_PATH = GOOGLE_DIR / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar",
]


def _get_credentials():
    """OAuth credentials 로드/갱신."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            logger.error(f"Token load error: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Refresh error: {e}")
                creds = None

        if not creds:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Google OAuth credentials not found at {CREDENTIALS_PATH}. "
                    f"Download from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Google token saved")

    return creds


def _get_service(name: str, version: str):
    """Google API 서비스 빌드."""
    from googleapiclient.discovery import build
    creds = _get_credentials()
    return build(name, version, credentials=creds, cache_discovery=False)


# ─── Gmail ────────────────────────────────────────────────────────────

def gmail_search(query: str = "is:unread", max_results: int = 10) -> str:
    """Gmail 검색. query 예: 'is:unread', 'from:name@example.com'."""
    try:
        service = _get_service("gmail", "v1")
        result = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            return "검색 결과 없음"

        lines = []
        for msg_ref in messages[:max_results]:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            lines.append(
                f"- [{headers.get('Date', '')[:16]}] {headers.get('From', '')}: "
                f"{headers.get('Subject', '(제목 없음)')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Gmail error: {e}"


def gmail_send(to: str, subject: str, body: str) -> str:
    """이메일 전송."""
    try:
        import base64
        from email.mime.text import MIMEText

        service = _get_service("gmail", "v1")
        msg = MIMEText(body, _charset="utf-8")
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        result = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return f"OK: 이메일 전송 완료 (id={result.get('id')})"
    except Exception as e:
        return f"Gmail send error: {e}"


# ─── Drive ────────────────────────────────────────────────────────────

def drive_search(query: str, max_results: int = 10) -> str:
    """Drive 파일 검색. query 예: 'name contains 보고서', 'mimeType=application/pdf'."""
    try:
        service = _get_service("drive", "v3")
        result = service.files().list(
            q=query, pageSize=max_results,
            fields="files(id,name,mimeType,modifiedTime)"
        ).execute()
        files = result.get("files", [])
        if not files:
            return "파일 없음"
        return "\n".join(
            f"- [{f.get('modifiedTime', '')[:10]}] {f['name']} ({f.get('mimeType', '?')})"
            for f in files
        )
    except Exception as e:
        return f"Drive error: {e}"


# ─── Calendar ─────────────────────────────────────────────────────────

def calendar_today() -> str:
    """오늘 일정 조회."""
    try:
        service = _get_service("calendar", "v3")
        now = datetime.now().astimezone()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True, orderBy="startTime",
        ).execute()
        events = result.get("items", [])

        if not events:
            return "오늘 일정 없음"

        lines = []
        for ev in events:
            start_str = ev["start"].get("dateTime", ev["start"].get("date", ""))
            lines.append(f"- {start_str[11:16]} {ev.get('summary', '(제목 없음)')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Calendar error: {e}"


def calendar_create(summary: str, start_iso: str, end_iso: str, description: str = "") -> str:
    """일정 생성. ISO 형식: '2026-04-25T14:00:00+09:00'."""
    try:
        service = _get_service("calendar", "v3")
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": "Asia/Seoul"},
            "end": {"dateTime": end_iso, "timeZone": "Asia/Seoul"},
        }
        result = service.events().insert(calendarId="primary", body=event).execute()
        return f"OK: 일정 생성 완료 ({result.get('htmlLink', '')})"
    except Exception as e:
        return f"Calendar create error: {e}"


# ─── 도구 스키마 ───────────────────────────────────────────────────────

GOOGLE_TOOLS_SCHEMA = [
    {
        "name": "gmail_search",
        "description": "Gmail 이메일을 검색합니다. 기본 'is:unread'로 안읽은 메일 조회.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색어 (예: 'is:unread', 'from:foo@bar.com')"},
                "max_results": {"type": "integer", "description": "최대 결과 수 (기본 10)"}
            },
        }
    },
    {
        "name": "gmail_send",
        "description": "이메일을 전송합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "수신자 이메일"},
                "subject": {"type": "string", "description": "제목"},
                "body": {"type": "string", "description": "본문"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "drive_search",
        "description": "Google Drive 파일을 검색합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색 쿼리 (예: 'name contains 보고서')"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "calendar_today",
        "description": "오늘의 캘린더 일정을 조회합니다.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "calendar_create",
        "description": "새 일정을 캘린더에 생성합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "제목"},
                "start_iso": {"type": "string", "description": "시작 시간 ISO 8601"},
                "end_iso": {"type": "string", "description": "종료 시간 ISO 8601"},
                "description": {"type": "string", "description": "설명 (선택)"}
            },
            "required": ["summary", "start_iso", "end_iso"]
        }
    },
]


def execute_google_tool(tool_name: str, tool_input: dict) -> str:
    """도구 이름 디스패치."""
    try:
        if tool_name == "gmail_search":
            return gmail_search(
                tool_input.get("query", "is:unread"),
                tool_input.get("max_results", 10),
            )
        elif tool_name == "gmail_send":
            return gmail_send(
                tool_input["to"], tool_input["subject"], tool_input["body"],
            )
        elif tool_name == "drive_search":
            return drive_search(tool_input["query"])
        elif tool_name == "calendar_today":
            return calendar_today()
        elif tool_name == "calendar_create":
            return calendar_create(
                tool_input["summary"],
                tool_input["start_iso"],
                tool_input["end_iso"],
                tool_input.get("description", ""),
            )
        return f"ERROR: 알 수 없는 도구 {tool_name}"
    except Exception as e:
        return f"ERROR: {e}"


def is_google_tool(name: str) -> bool:
    return name in {"gmail_search", "gmail_send", "drive_search", "calendar_today", "calendar_create"}
