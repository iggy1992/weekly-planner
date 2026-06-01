# 📋 Weekly Planner Bot

Slack으로 주간 할 일을 자동 관리해주는 GitHub Actions 봇입니다.

## 동작 방식

| 요일 | 시간 (KST) | 내용 |
|------|-----------|------|
| 월요일 | 09:00 | 이번 주 할 일 목록 발송 |
| 화~목 | 09:00 | 일일 진행 상황 점검 |
| 금요일 | 09:00 | 이번 주 결산 + 다음 주 계획 요청 |

## 셋업 (5분)

### 1. 레포 Fork / Clone

```bash
git clone https://github.com/YOUR_USERNAME/weekly-planner.git
cd weekly-planner
```

### 2. Slack Bot 토큰 발급

1. https://api.slack.com/apps → **Create New App** → From scratch
2. **OAuth & Permissions** → Bot Token Scopes에 추가:
   - `chat:write`
   - `chat:write.public`
3. **Install to Workspace** → `xoxb-...` 토큰 복사
4. 봇을 채널에 초대: `/invite @봇이름`

### 3. Slack 채널 ID 확인

Slack에서 채널 우클릭 → **채널 세부 정보 보기** → 맨 아래 채널 ID 복사  
형태: `C0XXXXXXXXX`

### 4. GitHub Secrets 등록

레포 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| 이름 | 값 |
|------|----|
| `SLACK_BOT_TOKEN` | `xoxb-...` |
| `SLACK_CHANNEL_ID` | `C0XXXXXXXXX` |

### 5. 할 일 등록

`data/tasks.json`을 편집하세요:

```json
{
  "week_start": "",
  "tasks": [
    { "id": 1, "text": "GEO SOV 리포트 작성", "tag": "마케팅", "done": false },
    { "id": 2, "text": "CRM 시나리오 검토",   "tag": "기획",   "done": false },
    { "id": 3, "text": "Confluence 인수인계서 업데이트", "tag": "업무", "done": false }
  ]
}
```

`tag` 옵션: `업무` / `기획` / `마케팅` / `개인` / `기타`

### 6. 완료 처리

`tasks.json`에서 완료한 항목의 `"done": true`로 변경 후 push하면  
다음 일일 점검 때 완료 상태로 발송됩니다.

```json
{ "id": 1, "text": "GEO SOV 리포트 작성", "tag": "마케팅", "done": true }
```

## 수동 실행 (테스트)

GitHub → **Actions** → **Weekly Planner Bot** → **Run workflow**  
mode 선택: `auto` / `monday` / `daily` / `friday`

## 파일 구조

```
weekly-planner/
├── .github/
│   └── workflows/
│       └── planner.yml     # GitHub Actions 크론 설정
├── scripts/
│   └── planner.py          # 핵심 로직
├── data/
│   └── tasks.json          # 할 일 데이터 (직접 편집)
└── README.md
```

## 다음 주 업무 흐름

```
금요일 09:00  → Slack에 "다음 주 계획 알려주세요" 메시지 수신
      ↓
data/tasks.json 수정 (다음 주 할 일 입력)
      ↓
git commit & push
      ↓
월요일 09:00  → Slack에 이번 주 할 일 목록 자동 발송
      ↓
매일 09:00    → 진행 상황 자동 점검
```
