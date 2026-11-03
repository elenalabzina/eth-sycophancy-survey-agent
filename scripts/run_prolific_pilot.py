"""Four participant Prolific pilot. Expose only port 8092 via Cloudflare Tunnel."""
from __future__ import annotations
import json,os,re,secrets,sqlite3,threading,time
from pathlib import Path
from urllib.parse import urlparse
from contextlib import contextmanager
from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
import uvicorn
from sycophancy_treatments.model import ChatModel,ModelConfig
from sycophancy_treatments.survey_agent import SurveyAgent,Session,OPENINGS

DB_PATH=Path(os.environ.get("PILOT_DB_PATH","private/prolific_pilot.sqlite"))
DURATION=int(os.environ.get("PILOT_DURATION_SECONDS","300"))
TOPIC=os.environ.get("PILOT_TOPIC","ai")
COMPLETION_URL=os.environ.get("PROLIFIC_COMPLETION_URL","")
PORT=int(os.environ.get("PILOT_PORT","8092"))
if TOPIC not in OPENINGS or not 60<=DURATION<=7200: raise RuntimeError("Invalid pilot topic or duration")
if COMPLETION_URL:
    parsed=urlparse(COMPLETION_URL)
    if parsed.scheme!="https" or parsed.hostname not in {"app.prolific.com","www.prolific.com","prolific.com"}:
        raise RuntimeError("Only official HTTPS Prolific completion URLs are supported")

app=FastAPI(title="AI Conversation Pilot",docs_url=None,redoc_url=None,openapi_url=None)
lock=threading.RLock()
agent=None

@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(DB_PATH),timeout=30)
    db.row_factory=sqlite3.Row
    try: yield db
    finally: db.close()

def initialize():
    with database() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS slots (
            position INTEGER PRIMARY KEY,
            condition TEXT NOT NULL CHECK (condition IN ('neutral','sycophantic')));
        CREATE TABLE IF NOT EXISTS participants (
            prolific_pid TEXT PRIMARY KEY,
            study_id TEXT, prolific_session_id TEXT,
            token TEXT NOT NULL UNIQUE, condition TEXT NOT NULL,
            topic TEXT NOT NULL, started_at REAL NOT NULL,
            messages_json TEXT NOT NULL DEFAULT '[]',
            finished_at REAL, slot INTEGER NOT NULL UNIQUE);
        """)
        n=db.execute("SELECT COUNT(*) FROM slots").fetchone()[0]
        if n==0:
            conditions=["neutral","neutral","sycophantic","sycophantic"]
            secrets.SystemRandom().shuffle(conditions)
            db.executemany("INSERT INTO slots(position,condition) VALUES (?,?)",enumerate(conditions))
        elif n!=4: raise RuntimeError("Invalid randomization table")
        db.commit()

@app.on_event("startup")
def startup():
    global agent
    initialize()
    config=os.environ.get("SURVEY_MODEL_CONFIG","configs/generator.example.yaml")
    agent=SurveyAgent(ChatModel(ModelConfig.from_yaml(config)),max_turns=40)

def public_state(row):
    transcript=json.loads(row["messages_json"])
    left=max(0,DURATION-int(time.time()-row["started_at"]))
    return {
        "messages":[{"role":"assistant","content":OPENINGS[row["topic"]]},*transcript],
        "remaining_seconds":left,"duration_seconds":DURATION,
        "finished":row["finished_at"] is not None,
        "can_finish":bool(transcript) or left==0,
        "completion_url":COMPLETION_URL if row["finished_at"] is not None else None
    }

def lookup(db,token):
    if not isinstance(token,str) or len(token)<30: raise HTTPException(401,"Invalid token")
    row=db.execute("SELECT * FROM participants WHERE token=?",(token,)).fetchone()
    if row is None: raise HTTPException(401,"Session not found")
    return row

@app.get("/",include_in_schema=False)
def page():
    html=Path(__file__).with_name("prolific_pilot.html").read_text(encoding="utf-8")
    return HTMLResponse(html,headers={"Cache-Control":"no-store"})

class Start(BaseModel):
    prolific_pid:str=Field(min_length=3,max_length=128)
    study_id:str=Field(default="",max_length=128)
    prolific_session_id:str=Field(default="",max_length=128)
    consent:bool

class Token(BaseModel):
    token:str

class Message(Token):
    text:str=Field(min_length=1,max_length=2000)

@app.post("/api/start")
def start(request:Start):
    if not request.consent:raise HTTPException(400,"Consent required")
    pid=request.prolific_pid.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,128}",pid):raise HTTPException(400,"Invalid participant ID")
    with lock,database() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM participants WHERE prolific_pid=?",(pid,)).fetchone():
            db.rollback()
            raise HTTPException(409,"This ID already has a session; use the original browser to resume.")
        slot=db.execute("""SELECT s.position,s.condition FROM slots s
            WHERE NOT EXISTS(SELECT 1 FROM participants p WHERE p.slot=s.position)
            ORDER BY s.position LIMIT 1""").fetchone()
        if slot is None:
            db.rollback()
            raise HTTPException(403,"Four-participant limit reached")
        token=secrets.token_urlsafe(32)
        db.execute("""INSERT INTO participants(prolific_pid,study_id,prolific_session_id,
            token,condition,topic,started_at,slot) VALUES(?,?,?,?,?,?,?,?)""",
            (pid,request.study_id,request.prolific_session_id,token,slot["condition"],TOPIC,time.time(),slot["position"]))
        db.commit()
        row=db.execute("SELECT * FROM participants WHERE token=?",(token,)).fetchone()
        return {"token":token,**public_state(row)}

@app.post("/api/state")
def state(data:Token):
    with database() as db:return public_state(lookup(db,data.token))

@app.post("/api/message")
def message(data:Message):
    if agent is None:raise HTTPException(503,"Model not ready")
    text=data.text.strip()
    if not text:raise HTTPException(400,"Empty message")
    with lock,database() as db:
        row=lookup(db,data.token)
        if row["finished_at"] is not None:raise HTTPException(409,"Conversation already finished")
        if time.time()-row["started_at"]>=DURATION:raise HTTPException(409,"Time limit reached")
        msgs=json.loads(row["messages_json"])
        if len(msgs)>=80:raise HTTPException(409,"Turn limit reached")
        if msgs and msgs[-1]["role"]=="user":
            if msgs[-1]["content"]!=text:raise HTTPException(409,"Please retry your pending message.")
        else:
            msgs.append({"role":"user","content":text})
            db.execute("UPDATE participants SET messages_json=? WHERE token=?",(json.dumps(msgs),data.token))
            db.commit()
        session_id=secrets.token_urlsafe(24)
        s=Session(condition=row["condition"],topic=row["topic"],duration_seconds=None)
        s.messages=msgs[:-1]
        agent.sessions[session_id]=s
        try: answer=agent.reply(session_id,text)["reply"]
        except Exception as exc:
            raise HTTPException(503,"AI temporarily unavailable; retry the same message.") from exc
        finally:agent.sessions.pop(session_id,None)
        msgs.append({"role":"assistant","content":answer})
        db.execute("UPDATE participants SET messages_json=? WHERE token=?",(json.dumps(msgs),data.token))
        db.commit()
        return public_state(db.execute("SELECT * FROM participants WHERE token=?",(data.token,)).fetchone())

@app.post("/api/finish")
def finish(data:Token):
    with lock,database() as db:
        row=lookup(db,data.token)
        if not public_state(row)["can_finish"]:raise HTTPException(409,"Send a message first")
        db.execute("UPDATE participants SET finished_at=COALESCE(finished_at,?) WHERE token=?",(time.time(),data.token))
        db.commit()
        return public_state(db.execute("SELECT * FROM participants WHERE token=?",(data.token,)).fetchone())

if __name__=="__main__":
    uvicorn.run(app,host="127.0.0.1",port=PORT,access_log=False)
