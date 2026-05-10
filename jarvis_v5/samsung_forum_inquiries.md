# Samsung Developer Forum 문의 추적

> 생성: 2026-04-26 (v1.3 권장값 일괄 승인 당일)
> 최종 점검: 2026-05-10 (2주차 점검)

---

## 문의 목록

### [문의 1] Bixby Plugin SDK — DAVIS Mobile 트리거 연동 가능성

| 항목 | 내용 |
|------|------|
| **포럼 URL** | https://developer.samsung.com/community |
| **카테고리** | Bixby / Plugin SDK |
| **문의 제목** | Can Bixby Plugin SDK trigger a foreground audio-capture service on Galaxy Z Flip5? |
| **문의 날짜** | 2026-04-26 |
| **디바이스** | SM-F731N (Galaxy Z Flip5), Android 16 / One UI 8.0 |
| **핵심 질문** | Bixby Routine이 "회의실 Wi-Fi 연결" 조건 감지 시 서드파티 ForegroundService를 직접 start할 수 있는지, 또는 BixbyPlugin으로 커스텀 캡슐을 통해 `ACTION_MANAGE_MEDIA`를 우회할 수 있는지 |
| **현재 상태** | ⏳ **응답 대기 중** (2026-05-10 기준, 13일 경과) |
| **응답 마감 목표** | 2026-05-17 (3주 미응답 시 삼성 개발자 이메일로 재문의) |

**문의 본문 요약**:
- DAVIS Mobile은 Z Flip5에서 상시 오디오 캡처(AudioRecord/MediaProjection)를 운영하는 ForegroundService를 사용
- 빅스비 루틴의 `Action → 앱 실행` 은 Activity만 트리거 가능한 것으로 보임
- Service를 직접 바인딩하거나 브로드캐스트로 깨우는 공식 SDK 경로가 있는지 확인 필요
- 대안으로 BroadcastReceiver + `ACTION_MEDIA_BUTTON` 또는 Shortcut API 활용 가능성도 확인 요청

---

### [문의 2] Knox SDK — 업무 프로파일 없이 AudioRecord 상시 실행 허용

| 항목 | 내용 |
|------|------|
| **포럼 URL** | https://developer.samsung.com/knox |
| **카테고리** | Knox SDK / Enterprise API |
| **문의 제목** | Can Knox SDK allow persistent AudioRecord in non-MDM personal deployment on Z Flip5? |
| **문의 날짜** | 2026-04-26 |
| **디바이스** | SM-F731N, 개인 기기 (MDM 미등록) |
| **핵심 질문** | Knox SDK의 `AudioManager` 정책 우회 없이, 개인 기기 환경에서 Android 14+ 오디오 캡처 제한(백그라운드 마이크 표시등 의무화)을 최소화하는 공식 패턴이 있는지 |
| **현재 상태** | ⏳ **응답 대기 중** (2026-05-10 기준, 13일 경과) |
| **응답 마감 목표** | 2026-05-17 |

**문의 본문 요약**:
- Android 14+에서 앱이 백그라운드 마이크를 사용하면 상단바에 녹색 점 표시 — 사용자가 알 수 있어 통비법 대응 가능
- Knox SDK `setMicMuteState()` / `setApplicationPermission()` 이 개인용 비MDM 기기에서도 동작하는지 (Knox SDK 3.x Personal Edition 범위 확인)
- 대안: `FOREGROUND_SERVICE_MICROPHONE` 타입 + 상시 알림으로 사용자에게 명시적으로 표시하는 방향이 Knox 없이도 충분한지 Samsung 권고 확인

---

## 후속 조치 계획

| 시점 | 조치 |
|------|------|
| 2026-05-17 | 미응답 시 각 문의에 댓글로 bump + 삼성 Developer Support 이메일 병행 |
| 2026-05-24 | 미응답 지속 시 → Bixby: `BroadcastReceiver + 루틴 Action` 폴백 확정, Knox: ForegroundService Notification 방식 확정 |

---

## 답변 수신 시 누적 섹션

> 답변 도착 시 아래에 추가

### [문의 1] Bixby Plugin SDK 답변

*(아직 없음)*

---

### [문의 2] Knox SDK 답변

*(아직 없음)*
