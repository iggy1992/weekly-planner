"""
Weekly Planner Agent
- Monday   : 이번 주 할 일 목록 발송
- Daily    : 매일 진행 상황 점검 발송
- Friday   : 다음 주 계획 요청 발송
"""

import json
import os
import sys
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


# ── 설정 ────────────────────────────────────────────────────────────────────

SLACK_TOKEN   = os.environ["SLACK_BOT_TOKEN"]       # secrets.SLACK_BOT_TOKEN
SLACK_CHANNEL = os.environ["SLACK_CHANNEL_ID"]      # secrets.SLACK_CHANNEL_ID
DATA_FILE     = Path(__file__).parent.parent / "data" / "tasks.json"

HEADERS = {
    "Authorization": f"Bearer {SLACK_TOKEN}",
    "Content-Type": "application/json; charset=utf-8",
}


# ── 데이터 ───────────────────────────────────────────────────────────────────

def load_tasks() -> dict:
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_tasks(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def reset_week_if_needed(data: dict) -> dict:
    """새 주가 시작되면 done 상태 초기화 + week_start 갱신"""
    today = date.today()
    monday = get_monday(today)
    monday_str = monday.isoformat()

    if data.get("week_start") != monday_str:
        # 완료 상태 초기화 (태스크 목록은 유지 — 필요시 직접 편집)
        for t in data["tasks"]:
            t["done"] = False
        data["week_start"] = monday_str
        save_tasks(data)
        print(f"[INFO] 새 주 시작: {monday_str}, done 상태 초기화 완료")

    return data


# ── Slack ────────────────────────────────────────────────────────────────────

def send_slack(blocks: list, text: str = "") -> None:
    payload = {
        "channel": SLACK_CHANNEL,
        "text": text,       # 알림 미리보기용 fallback
        "blocks": blocks,
    }
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers=HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Slack API error: {result.get('error')}")
    print(f"[OK] Slack 발송 완료 → {SLACK_CHANNEL}")


def divider() -> dict:
    return {"type": "divider"}


def section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def header(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text, "emoji": True}}


# ── 모드별 메시지 ─────────────────────────────────────────────────────────────

def send_monday(data: dict) -> None:
    today = date.today()
    monday = get_monday(today)
    friday = monday + timedelta(days=4)

    tasks = data["tasks"]
    if not tasks:
        print("[WARN] 태스크가 없습니다. data/tasks.json에 할 일을 추가하세요.")
        return

    tag_map: dict[str, list] = {}
    for t in tasks:
        tag_map.setdefault(t.get("tag", "기타"), []).append(t["text"])

    task_lines = "\n".join(
        f"{'✅' if t['done'] else '⬜'}  {t['text']}  `{t.get('tag','기타')}`"
        for t in tasks
    )

    blocks = [
        header(f"📋  이번 주 할 일  ({monday.month}/{monday.day} ~ {friday.month}/{friday.day})"),
        divider(),
        section(task_lines),
        divider(),
        section(f"총 *{len(tasks)}개* | 좋은 한 주 시작해요 🚀"),
    ]
    send_slack(blocks, text=f"📋 이번 주 할 일 ({len(tasks)}개)")


def send_daily(data: dict) -> None:
    today = date.today()
    day_ko = ["월", "화", "수", "목", "금", "토", "일"][today.weekday()]
    date_str = f"{today.month}/{today.day}({day_ko})"

    tasks = data["tasks"]
    done   = [t for t in tasks if t["done"]]
    undone = [t for t in tasks if not t["done"]]
    pct    = round(len(done) / len(tasks) * 100) if tasks else 0

    bar_filled = round(pct / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    done_text   = "\n".join(f"✅  ~{t['text']}~" for t in done)   or "아직 없음"
    undone_text = "\n".join(f"⬜  {t['text']}" for t in undone) or "모두 완료! 🎉"

    if pct >= 80:
        comment = "대단한데요, 거의 다 왔어요! 🎉"
    elif pct >= 50:
        comment = "절반 이상 완료! 꾸준히 가요 💪"
    else:
        comment = "오늘 더 달려봐요 ⚡️"

    blocks = [
        header(f"📊  일일 점검  —  {date_str}"),
        divider(),
        section(f"*완료 ({len(done)}개)*\n{done_text}"),
        divider(),
        section(f"*미완료 ({len(undone)}개)*\n{undone_text}"),
        divider(),
        section(f"`{bar}` *{pct}%*   {comment}"),
    ]
    send_slack(blocks, text=f"📊 일일 점검 — 완료율 {pct}%")


def send_friday(data: dict) -> None:
    today   = date.today()
    monday  = get_monday(today)
    tasks   = data["tasks"]
    done    = [t for t in tasks if t["done"]]
    pct     = round(len(done) / len(tasks) * 100) if tasks else 0

    next_mon = monday + timedelta(weeks=1)
    next_fri = next_mon + timedelta(days=4)

    blocks = [
        header(f"📅  이번 주 마무리 & 다음 주 계획"),
        divider(),
        section(
            f"이번 주 완료율: *{pct}%*  ({len(done)}/{len(tasks)}개)\n"
            + ("수고했어요! 정말 잘 해냈습니다 🙌" if pct >= 80 else "다음 주엔 더 잘 할 수 있어요 💪")
        ),
        divider(),
        section(
            f"*다음 주 ({next_mon.month}/{next_mon.day} ~ {next_fri.month}/{next_fri.day}) 할 일을 `data/tasks.json`에 업데이트해 주세요!*\n\n"
            "```\n"
            "{\n"
            '  "tasks": [\n'
            '    { "id": 1, "text": "할 일 내용", "tag": "업무", "done": false }\n'
            "  ]\n"
            "}\n"
            "```\n"
            "👉 파일 수정 후 `main` 브랜치에 push하면 다음 주 월요일 아침 자동 발송됩니다."
        ),
    ]
    send_slack(blocks, text=f"📅 이번 주 마무리 — 완료율 {pct}%")


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly Planner Slack Bot")
    parser.add_argument(
        "mode",
        choices=["monday", "daily", "friday", "auto"],
        help="auto = 요일에 따라 자동 판단",
    )
    args = parser.parse_args()

    data = load_tasks()
    data = reset_week_if_needed(data)

    mode = args.mode
    if mode == "auto":
        weekday = date.today().weekday()   # 0=월 … 6=일
        if weekday == 0:
            mode = "monday"
        elif weekday == 4:
            mode = "friday"
        else:
            mode = "daily"

    print(f"[INFO] mode={mode}, today={date.today()}")

    if mode == "monday":
        send_monday(data)
    elif mode == "daily":
        send_daily(data)
    elif mode == "friday":
        send_friday(data)


if __name__ == "__main__":
    main()
