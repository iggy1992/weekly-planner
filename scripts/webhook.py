import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs

import requests
from fastapi import FastAPI, Request, Response

app = FastAPI()

SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN_TASKS"]
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")  # e.g. "username/weekly-planner"
TASKS_PATH = "data/tasks.json"
GITHUB_API_BASE = "https://api.github.com"


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    computed = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def github_headers() -> dict:
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def get_tasks() -> tuple[dict, str]:
    """Fetch tasks.json from GitHub. Returns (data, sha)."""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{TASKS_PATH}"
    resp = requests.get(url, headers=github_headers())
    resp.raise_for_status()
    payload = resp.json()
    import base64
    content = base64.b64decode(payload["content"]).decode("utf-8")
    return json.loads(content), payload["sha"]


def put_tasks(data: dict, sha: str, message: str) -> None:
    """Write tasks.json back to GitHub."""
    import base64
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/contents/{TASKS_PATH}"
    body = {
        "message": message,
        "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(),
        "sha": sha,
    }
    resp = requests.put(url, headers=github_headers(), json=body)
    resp.raise_for_status()


def handle_add(text: str) -> str:
    """Parse '/할일 [내용] [태그]' and add a task."""
    parts = text.strip().rsplit(" ", 1)
    known_tags = {"회사", "개인", "교회", "기타"}
    if len(parts) == 2 and parts[1] in known_tags:
        task_text, tag = parts[0].strip(), parts[1]
    else:
        task_text, tag = text.strip(), "기타"

    if not task_text:
        return "할 일 내용을 입력해 주세요. 예) `/할일 보고서 작성 회사`"

    data, sha = get_tasks()
    tasks = data.get("tasks", [])
    new_id = max((t["id"] for t in tasks), default=0) + 1
    tasks.append({"id": new_id, "text": task_text, "tag": tag, "done": False})
    data["tasks"] = tasks
    put_tasks(data, sha, f"Add task #{new_id}: {task_text}")
    return f"✅ 추가됨: *[{new_id}] {task_text}* (태그: {tag})"


def handle_done(text: str) -> str:
    """Parse '/완료 [번호]' and mark task done."""
    text = text.strip()
    if not text.isdigit():
        return "번호를 입력해 주세요. 예) `/완료 3`"

    task_id = int(text)
    data, sha = get_tasks()
    tasks = data.get("tasks", [])
    target = next((t for t in tasks if t["id"] == task_id), None)
    if target is None:
        return f"번호 {task_id}에 해당하는 할 일이 없습니다."
    if target["done"]:
        return f"이미 완료된 항목입니다: *[{task_id}] {target['text']}*"

    target["done"] = True
    data["tasks"] = tasks
    put_tasks(data, sha, f"Complete task #{task_id}: {target['text']}")
    return f"🎉 완료 처리됨: *[{task_id}] {target['text']}*"


def handle_list() -> str:
    """Return formatted task list."""
    data, _ = get_tasks()
    tasks = data.get("tasks", [])
    if not tasks:
        return "등록된 할 일이 없습니다."

    pending = [t for t in tasks if not t["done"]]
    done = [t for t in tasks if t["done"]]

    lines = []
    if pending:
        lines.append("*📋 할 일 목록*")
        for t in pending:
            lines.append(f"  `[{t['id']}]` {t['text']}  _{t['tag']}_")
    if done:
        lines.append("*✅ 완료된 항목*")
        for t in done:
            lines.append(f"  ~[{t['id']}] {t['text']}~  _{t['tag']}_")

    total = len(tasks)
    lines.append(f"\n전체 {total}개 중 {len(done)}개 완료")
    return "\n".join(lines)


@app.post("/slack/commands")
async def slack_commands(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body, timestamp, signature):
        return Response(content="Unauthorized", status_code=401)

    params = parse_qs(body.decode())
    command = params.get("command", [""])[0]
    text = params.get("text", [""])[0].strip()

    try:
        if command in ("/할일", "/task"):
            msg = handle_add(text)
        elif command in ("/완료", "/done"):
            msg = handle_done(text)
        elif command in ("/목록", "/list"):
            msg = handle_list()
        else:
            msg = f"알 수 없는 커맨드: `{command}`"
    except Exception as e:
        msg = f"오류가 발생했습니다: {e}"

    return {
        "response_type": "ephemeral",
        "text": msg,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
