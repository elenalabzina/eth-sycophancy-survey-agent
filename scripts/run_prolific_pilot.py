"""Blinded ten-minute human pilot for invited Prolific participants.

Run from repository root with the Qwen-compatible model server running.
Never commit the private assignments JSON or resulting SQLite file.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

from sycophancy_treatments.model import ChatModel, ModelConfig
from sycophancy_treatments.survey_agent import OPENINGS, Session, SurveyAgent

ROOT = Path(__file__).resolve().parents[1]
DURATION = 600
TOPIC = "ai"
INTRO = (
    "Governments are considering whether developers of advanced AI systems "
    "should be required to pass independent safety evaluations before releasing "
    "them. Supporters argue that these checks could reduce harm and strengthen "
    "accountability. Critics worry that mandatory reviews might slow innovation "
    "and place a greater burden on smaller developers. There is no universally "
    "agreed approach. What is your view, and which trade-offs matter most?"
)
PID_RE = re.compile(r"^[a-fA-F0-9]{24}$")
app = FastAPI(title="AI Policy Conversation Study", docs_url=None, redoc_url=None)
agent: SurveyAgent | None = None
gate = threading.RLock()

def store_path() -> Path:
    return Path(os.environ.get("PILOT_DB", "outputs/prolific_pilot.sqlite"))

def connect():
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def assignments() -> dict:
    path = Path(os.environ.get("PILOT_ASSIGNMENTS_FILE", "private/pilot_assignments.json"))
    if not path.is_file():
        raise RuntimeError(f"Private pilot assignments missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))["participants"]
    if len(data) != 4 or any(not PID_RE.fullmatch(pid) for pid in data):
        raise RuntimeError("Pilot assignments must contain four valid Prolific participant IDs")
    cells = sorted((x["group"], x["condition"]) for x in data.values())
    expected = sorted([(g, c) for g in ("higher", "lower") for c in ("neutral", "sycophantic")])
    if cells != expected:
        raise RuntimeError("Pilot assignments must have one participant in each 2×2 cell")
    return data

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS pilot_sessions (
          pid TEXT PRIMARY KEY,
          token TEXT NOT NULL UNIQUE,
          study_id TEXT,
          submission_id TEXT,
          group_name TEXT NOT NULL,
          condition_name TEXT NOT NULL,
          started REAL NOT NULL,
          baseline_stance INTEGER NOT NULL,
          baseline_confidence INTEGER NOT NULL,
          finished REAL,
          post_stance INTEGER,
          post_confidence INTEGER,
          reflection TEXT
        );
        CREATE TABLE IF NOT EXISTS pilot_messages (
          pid TEXT NOT NULL,
          seq INTEGER NOT NULL,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          timestamp REAL NOT NULL,
          PRIMARY KEY(pid, seq)
        );
        """)

def require_row(token: str):
    if not isinstance(token, str) or len(token) > 150 or len(token) < 30:
        raise HTTPException(401, "Invalid session token")
    with connect() as db:
        row = db.execute("SELECT * FROM pilot_sessions WHERE token=?", (token,)).fetchone()
    if row is None:
        raise HTTPException(401, "Unknown session")
    return dict(row)

def view(row):
    with connect() as db:
        msgs = db.execute(
            "SELECT role,content FROM pilot_messages WHERE pid=? ORDER BY seq",
            (row["pid"],)
        ).fetchall()
    return {
        "opening": OPENINGS[TOPIC],
        "introduction": INTRO,
        "messages": [dict(m) for m in msgs],
        "remaining_seconds": max(0, int(DURATION - (time.time() - row["started"]))),
        "finished": row["finished"] is not None,
        "session_started": row["started"],
        # Deliberately omit condition_name, group_name and private metadata.
    }

def completion_url():
    url = os.environ.get("PILOT_COMPLETION_URL", "").strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "app.prolific.com" or not parts.path.startswith("/submissions/complete"):
        return None
    return url

class StartRequest(BaseModel):
    prolific_pid: str = Field(min_length=24, max_length=24)
    study_id: str | None = Field(default=None, max_length=128)
    submission_id: str | None = Field(default=None, max_length=128)
    resume_token: str | None = None
    baseline_stance: int = Field(ge=0, le=100)
    baseline_confidence: int = Field(ge=0, le=100)

class MessageRequest(BaseModel):
    token: str
    message: str = Field(min_length=1, max_length=2000)

class FinishRequest(BaseModel):
    token: str
    post_stance: int = Field(ge=0, le=100)
    post_confidence: int = Field(ge=0, le=100)
    reflection: str = Field(default="", max_length=4000)

@app.on_event("startup")
def startup():
    global agent
    if not completion_url() and os.environ.get("PILOT_ALLOW_NO_COMPLETION_URL") != "1":
        raise RuntimeError("Set PILOT_COMPLETION_URL to the completion URL shown in Prolific before recruiting.")
    assignments()
    init_db()
    cfg = os.environ.get("SURVEY_MODEL_CONFIG", "configs/generator.example.yaml")
    agent = SurveyAgent(ChatModel(ModelConfig.from_yaml(cfg)), max_turns=40, duration_seconds=DURATION)

@app.get("/", include_in_schema=False)
def landing():
    return HTMLResponse((ROOT / "scripts" / "prolific_pilot.html").read_text(encoding="utf-8"))

@app.post("/api/start")
def start(req: StartRequest):
    pid = req.prolific_pid.lower()
    cell = assignments().get(pid)
    if cell is None:
        raise HTTPException(403, "This pilot is limited to invited participants.")
    with gate:
        with connect() as db:
            row = db.execute("SELECT * FROM pilot_sessions WHERE pid=?", (pid,)).fetchone()
            if row is not None:
                if req.resume_token != row["token"] or req.submission_id != row["submission_id"]:
                    raise HTTPException(409, "A study session already exists for this participant.")
                return {"token": row["token"], **view(dict(row))}
            token = secrets.token_urlsafe(36)
            now = time.time()
            db.execute(
                """INSERT INTO pilot_sessions
                (pid,token,study_id,submission_id,group_name,condition_name,started,baseline_stance,baseline_confidence)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (pid,token,req.study_id,req.submission_id,cell["group"],cell["condition"],
                 now,req.baseline_stance,req.baseline_confidence)
            )
            db.commit()
        return {"token": token, **view(require_row(token))}

@app.post("/api/state")
def state(req: MessageRequest):
    return view(require_row(req.token))

def restore(row):
    assert agent is not None
    token = row["token"]
    if token in agent.sessions:
        return
    elapsed = max(0, time.time()-row["started"])
    with connect() as db:
        messages = [
            dict(m) for m in db.execute(
                "SELECT role,content FROM pilot_messages WHERE pid=? ORDER BY seq",
                (row["pid"],)
            ).fetchall()
        ]
    agent.sessions[token] = Session(
        condition=row["condition_name"], topic=TOPIC,
        messages=messages, started_at=time.monotonic()-elapsed,
        duration_seconds=DURATION, internet_access=False
    )

@app.post("/api/chat")
def chat(req: MessageRequest):
    row = require_row(req.token)
    with gate:
        row = require_row(req.token)
        if row["finished"] is not None:
            raise HTTPException(409, "This study session has finished.")
        if time.time()-row["started"] >= DURATION:
            raise HTTPException(409, "The ten-minute conversation has ended.")
        restore(row)
        try:
            result = agent.reply(row["token"], req.message)
        except (ValueError, KeyError) as exc:
            raise HTTPException(400, str(exc))
        # Persist the actual human and model turns; never send hidden condition to the browser.
        with connect() as db:
            cur = db.execute(
                "SELECT COALESCE(MAX(seq),-1)+1 FROM pilot_messages WHERE pid=?",
                (row["pid"],)
            )
            idx = cur.fetchone()[0]
            now = time.time()
            db.executemany(
                "INSERT INTO pilot_messages(pid,seq,role,content,timestamp) VALUES(?,?,?,?,?)",
                [(row["pid"],idx,"user",req.message.strip(),now),
                 (row["pid"],idx+1,"assistant",result["reply"],time.time())]
            )
            db.commit()
        return {"reply":result["reply"],"remaining_seconds":max(0,int(DURATION-(time.time()-row["started"])))}

@app.post("/api/finish")
def finish(req: FinishRequest):
    with gate:
        row = require_row(req.token)
        if time.time()-row["started"] < DURATION and row["finished"] is None:
            raise HTTPException(409, "The conversation is still in progress.")
        if row["finished"] is None:
            with connect() as db:
                db.execute(
                    "UPDATE pilot_sessions SET finished=?,post_stance=?,post_confidence=?,reflection=? WHERE token=?",
                    (time.time(),req.post_stance,req.post_confidence,req.reflection,req.token)
                )
                db.commit()
        return {"finished":True, "completion_url": completion_url()}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8092, access_log=False)
