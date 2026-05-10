# DAVIS Mobile Phase 2 — PR 체크리스트 초안

> 작성: 2026-05-10 (2주차 점검, v1.3 권장값 승인 2026-04-26 기준)
> 상태: **초안** — 박대표 승인 후 PR 생성
> 디바이스: Galaxy Z Flip5 (SM-F731N / R3CW90H3CXM, Android 16 / One UI 8.0)

---

## 공통 사전 조건 (모든 항목 공통)

- [ ] `adb devices` 결과에 `R3CW90H3CXM` 표시 (USB 디버깅 활성 확인)
- [ ] Hub(집 노트북)에서 `python -m jarvis_v5.jarvis` 정상 기동 확인
- [ ] `.env` 파일에 `ANTHROPIC_API_KEY` / `TELEGRAM_BOT_TOKEN` 유효 확인
- [ ] Tailscale 클라이언트가 Hub와 Z Flip5 양쪽에서 Connected 상태

---

## a. 빅스비 루틴 트리거 명세

> 정책: **제안 알림 only** (v1.2 정책 준수 — 앱 자동 강제 실행 금지, 사용자가 알림 탭해서 시작)

### 사전 조건

- [ ] Z Flip5에 DAVIS Mobile APK 설치 완료 (`adb install -r app-debug.apk`)
- [ ] 빅스비 루틴 앱 버전 ≥ 3.0 (One UI 8.0 기본 탑재 확인)
- [ ] DAVIS Mobile 앱에 `POST_NOTIFICATIONS` 권한 허용

### 트리거 명세 (루틴 조건 → 액션)

| 루틴 이름 | 조건 | 액션 | 비고 |
|-----------|------|------|------|
| `davis_meeting_wifi` | 특정 Wi-Fi SSID 연결 (회의실용) | 알림: "데비스 청취 시작할까요?" | 사용자 탭 → DavisListenerService 시작 |
| `davis_flex_mode` | 폴더블 반접기 감지 (Flex Mode) | 알림: "책상 거치 감지 — 데비스 활성화?" | `ACTION_FOLD_STATE` 브로드캐스트 수신 |
| `davis_calendar_meeting` | 캘린더 이벤트 5분 전 | 알림: "곧 {이벤트명} 시작 — 데비스 준비?" | Google Calendar API 연동 |
| `davis_side_key` | 전원 버튼 2회 누르기 | 알림 없이 앱 전면 실행 (사용자가 직접 트리거) | 빅스비 루틴 예외 — 명시적 수동 액션 |

### 검증 명령어

```bash
# 루틴 BroadcastReceiver 수신 확인
adb logcat -d | grep -i 'DavisRoutineReceiver\|BixbyRoutine'

# 알림 발송 확인
adb shell dumpsys notification --noredact | grep -A5 'davis'

# 서비스 기동 상태 확인 (알림 탭 후)
adb shell dumpsys activity services | grep 'DavisListenerService'
```

### 예상 결과

```
DavisRoutineReceiver: received ACTION=davis.ROUTINE_TRIGGER
NotificationManager: posted channel=davis_triggers id=1001
DavisListenerService: onCreate() state=LISTENING
```

### 실패 시 폴백

- 빅스비 루틴 조건 미지원 → `AlarmManager` 기반 캘린더 폴링 + 직접 알림
- ForegroundService 시작 불가(백그라운드 제한) → Activity로 대신 실행 후 Service 위임

---

## b. Cover Screen 위젯 실 활성화

> `widget/DavisCoverWidget.kt` 이미 작성 완료. 박대표 폰에서 위젯 추가 시연 단계.

### 사전 조건

- [ ] `DavisCoverWidget.kt`가 APK에 포함되어 빌드됨
- [ ] `AndroidManifest.xml`에 `<receiver android:name=".widget.DavisCoverWidget">` 등록 확인
- [ ] Z Flip5에 APK 설치 완료

### 검증 순서 (박대표 직접 수행)

1. 폰을 **접은 상태**에서 커버 화면 길게 누르기 → "위젯 편집" 진입
2. 위젯 목록에서 **"DAVIS"** 확인 후 추가 (3.4" Flex Window 최적화 크기: 2×1)
3. 커버 화면에서 DAVIS 위젯 표시 확인:
   - 상태 표시: `● 대기 중` / `● 청취 중` / `● 연결 끊김`
   - 마지막 전사 한 줄 스크롤 (청취 세션 활성 시)

### 검증 명령어

```bash
# 위젯 브로드캐스트 강제 트리거
adb shell am broadcast -a android.appwidget.action.APPWIDGET_UPDATE \
  -n com.davis.mobile/.widget.DavisCoverWidget

# 위젯 provider 등록 확인
adb shell dumpsys appwidget | grep -i 'davis'

# 커버 화면 렌더링 로그
adb logcat -d | grep -i 'DavisCoverWidget\|CoverScreen'
```

### 예상 결과

```
AppWidgetManager: update widget id=X provider=DavisCoverWidget
DavisCoverWidget: onUpdate() views=RemoteViews{status=STANDBY}
```

### 실패 시 폴백

- 커버 화면 위젯 API 미지원(One UI 버전 문제) → 메인 화면 홈스크린 위젯으로 대체
- 위젯 목록 미노출 → `android:exported="true"` 및 `BIND_APPWIDGET` 권한 재확인
- Samsung Cover Screen API 별도 허가 필요 시 → Samsung Galaxy SDK (Galaxy Store 제출 없이 사이드로드용 커버 위젯 API 활성화 방법 확인 필요)

---

## c. Tailscale Funnel 외출 테스트

> Hub(집 노트북) ↔ Z Flip5, SKT 5G 환경에서 페어링 + WSS RTT 측정

### 사전 조건

- [ ] Hub에서 `scripts/davis_tunnel.sh` 존재 및 실행 권한 확인
  ```bash
  ls -la scripts/davis_tunnel.sh
  # 없으면 아래 단계로 생성
  ```
- [ ] Hub에서 Tailscale 로그인 상태: `tailscale status`
- [ ] `sync_server` 실행 중: `curl http://localhost:8443/api/v1/health`
- [ ] Z Flip5 Tailscale 앱 설치 + 동일 계정 로그인

### davis_tunnel.sh 내용 (미존재 시 생성)

```bash
#!/usr/bin/env bash
# Hub에서 실행 — DAVIS Sync Server를 Tailscale Funnel로 외부 노출
set -euo pipefail

ACTION="${1:-on}"

if [[ "$ACTION" == "on" ]]; then
  echo "[davis_tunnel] Tailscale Funnel 활성화..."
  tailscale funnel 8443
  echo "[davis_tunnel] Funnel 주소:"
  tailscale funnel status
elif [[ "$ACTION" == "off" ]]; then
  tailscale funnel --bg=false 8443 off 2>/dev/null || true
  echo "[davis_tunnel] Funnel 비활성화 완료"
fi
```

### 검증 명령어 (Hub — scripts/davis_tunnel.sh on 실행 후)

```bash
# 1. Funnel 주소 확인
tailscale funnel status
# 예상: https://<hostname>.ts.net → localhost:8443

# 2. 외부 주소로 헬스체크 (Hub에서)
curl -sk https://<hostname>.ts.net/api/v1/health | python3 -m json.tool
# 예상: {"status":"ok","version":"1.x"}

# 3. WSS RTT 측정 (Hub에서, wscat 또는 Python 사용)
python3 -c "
import asyncio, time, websockets

async def ping():
    url = 'wss://<hostname>.ts.net/ws/v1/audio'
    start = time.monotonic()
    async with websockets.connect(url) as ws:
        await ws.send('{\"type\":\"ping\"}')
        resp = await ws.recv()
        rtt = (time.monotonic() - start) * 1000
        print(f'WSS RTT: {rtt:.1f}ms  resp={resp}')

asyncio.run(ping())
"
```

### Z Flip5에서 수행 (SKT 5G 전환 후)

```bash
# Wi-Fi 비활성화 확인 (SKT 5G 강제)
adb shell svc wifi disable

# 앱 실행 후 페어링 화면에서 Funnel 주소 입력
# Logcat에서 연결 확인
adb logcat -d | grep -iE 'davis.*wss|tunnel|funnel|RTT'
```

### 예상 결과

| 환경 | 목표 RTT | 허용 상한 |
|------|----------|-----------|
| 동일 Wi-Fi (LAN) | < 20ms | 50ms |
| Tailscale (Wi-Fi) | < 50ms | 100ms |
| Tailscale + SKT 5G | < 120ms | 200ms |

### 실패 시 폴백

- Funnel 미지원 플랜 → `tailscale serve` (내부 메시만) + 공유기 포트포워딩 대안
- RTT > 200ms (SKT 5G) → Funnel 대신 DDNS(DuckDNS) + Nginx SSL 종단 구성
- mTLS 인증 실패 → `DAVIS_SKIP_MTLS=1` 환경변수로 임시 우회 후 원인 파악

---

## d. 페어링 E2E 검증

> pair-code → QR → PairingScreen → /ws/v1/audio chunk → /api/v1/sessions

### 사전 조건

- [ ] Hub: `sync_server` 실행 중 (`curl http://localhost:8443/api/v1/health` → `{"status":"ok"}`)
- [ ] Hub: `/api/v1/pair/generate` 엔드포인트 구현 완료
- [ ] Z Flip5: DAVIS Mobile APK 최신 빌드 설치
- [ ] Tailscale or LAN 연결 확인

### 페어링 시퀀스

```
[Hub]                              [Z Flip5]
  │                                    │
  │ POST /api/v1/pair/generate         │
  │ → {pair_code: "XXXX", qr_data: "…"}│
  │                                    │
  │          QR 코드 표시               │
  │ ←────────────────────────────────  │ 카메라로 QR 스캔
  │                                    │
  │ POST /api/v1/pair/confirm          │
  │ → {device_token: "eyJ…", device_id: "…"}
  │                                    │
  │ WS /ws/v1/audio (Bearer token)     │
  │ ←── PCM chunk (16kHz 모노) ──────  │
  │                                    │
  │ GET /api/v1/sessions               │
  │ → [{session_id, start_time, …}]   │
```

### 검증 명령어

```bash
# 1. pair-code 발급 (Hub에서)
curl -s http://localhost:8443/api/v1/pair/generate | python3 -m json.tool
# 예상: {"pair_code":"ABCD","qr_data":"...","expires_in":300}

# 2. 페어링 확인 (Z Flip5 QR 스캔 후 Hub에서)
curl -s http://localhost:8443/api/v1/pair/status | python3 -m json.tool
# 예상: {"status":"paired","device_id":"R3CW90H3CXM"}

# 3. 세션 목록 (음성 chunk 1개 이상 수신 후)
curl -s -H "Authorization: Bearer <device_token>" \
  http://localhost:8443/api/v1/sessions | python3 -m json.tool
# 예상: [{"session_id":"...","chunk_count":N,"started_at":"..."}]

# 4. Z Flip5 Logcat — 오디오 chunk 전송 확인
adb logcat -d | grep -iE 'davis.*(chunk|audio|send|wss)'
# 예상: DavisAudioStreamer: sent chunk #N size=3200bytes latency=Xms

# 5. Hub Logcat (sync_server) — chunk 수신 확인
grep -i 'chunk\|session\|audio' ~/.jarvis-cc/logs/sync_server.log | tail -20
```

### 예상 결과 (전체 플로우 성공)

```
[Hub] pair_code generated: ABCD (expires: 300s)
[Flip5] QR scanned → POST /api/v1/pair/confirm → device_token=eyJ…
[Flip5] WS /ws/v1/audio connected
[Flip5] DavisAudioStreamer: sent chunk #1 size=3200 latency=45ms
[Hub] received chunk #1 session_id=sess_001 bytes=3200
[Hub] session created: sess_001 device=R3CW90H3CXM
```

### 실패 시 폴백

| 실패 지점 | 원인 | 폴백 |
|-----------|------|------|
| QR 스캔 불가 | 카메라 권한 / QR 라이브러리 미통합 | 수동 pair-code 6자리 입력 UI 추가 |
| `/api/v1/pair/confirm` 401 | 토큰 만료(5분) | 재발급 버튼 + 만료 안내 |
| WSS 연결 끊김 | 네트워크 불안정 | 지수 백오프 재연결 (2s→4s→8s→max 60s) |
| chunk 수신 안됨 | AudioRecord 권한 누락 | `RECORD_AUDIO` 권한 재요청 다이얼로그 |
| 세션 미생성 | sync_server 버그 | `~/.jarvis-cc/logs/sync_server.log` 확인 후 이슈 등록 |

---

## PR 생성 전 최종 게이트

- [ ] **a. 빅스비 루틴**: 루틴 알림 발송 + 서비스 기동 Logcat 캡처 첨부
- [ ] **b. 커버 위젯**: 커버 화면 위젯 표시 스크린샷 첨부
- [ ] **c. Funnel RTT**: SKT 5G 환경 RTT 측정값 표 첨부 (목표: < 200ms)
- [ ] **d. 페어링 E2E**: 세션 생성 curl 응답 + Logcat 스크린샷 첨부
- [ ] `ruff check jarvis_v5/` 무경고
- [ ] `pytest -q tests/` 통과
- [ ] Conventional Commits 메시지 (`feat(mobile): phase2 validation complete`)

> 박대표 최종 승인 후 PR 생성 — `git push -u origin feat/mobile-phase2-validation`
