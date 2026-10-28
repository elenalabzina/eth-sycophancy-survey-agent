"""Local-only API for survey agent. Start MLX server separately on :8080.

Install: pip install -e '.[server]'
Run: python scripts/run_survey_server.py
Test at http://127.0.0.1:8090/docs
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
from sycophancy_treatments.model import ChatModel, ModelConfig
from sycophancy_treatments.survey_agent import SurveyAgent, OPENINGS
from sycophancy_treatments.web_tools import search_and_read


app = FastAPI(title="ETH Survey Agent — local prototype", docs_url="/docs")
agent: SurveyAgent | None = None


class ChatIn(BaseModel):
    session_id: str
    message: str = Field(min_length=1,max_length=2000)


class StartIn(BaseModel):
    # Only for developer testing. Production assignment must be server-side.
    condition: str | None = None
    topic: str = "ai"
    duration_seconds: int | None = 300
    internet_access: bool = False


@app.on_event("startup")
def startup():
    global agent
    config = os.environ.get("SURVEY_MODEL_CONFIG","configs/generator.example.yaml")
    model = ChatModel(ModelConfig.from_yaml(config))
    search = search_and_read if os.environ.get("ENABLE_WEB_SEARCH","0") == "1" else None
    agent = SurveyAgent(model, search=search)


@app.get("/", include_in_schema=False)
def chat_page():
    page = Path(__file__).with_name("survey_chat.html").read_text(encoding="utf-8")
    page = page.replace(
        '<select id="duration"><option value="300">5 minutes</option><option value="unlimited">Unlimited</option></select>',
        '<input id="duration" type="number" value="5" min="1" max="120" step="1" style="width:75px;padding:9px"> min <label><input id="unlimited" type="checkbox"> Unlimited</label>',
    )
    page = page.replace(
        "ui.duration.value==='unlimited'?null:300",
        "(document.querySelector('#unlimited').checked?null:validatedMinutes()*60)",
    )
    page = page.replace(
        "ui.duration.value==='unlimited'?'No time limit':'05:00'",
        "document.querySelector('#unlimited').checked?'No time limit':formatDuration(validatedMinutes()*60)",
    )
    page = page.replace(
        "ui.clock.textContent=deadline?'05:00':'No time limit';",
        "ui.clock.textContent=deadline?formatDuration(d.duration_seconds):'No time limit';",
    )
    page = page.replace(
        "ui.duration.disabled=value;",
        "ui.duration.disabled=value||document.querySelector('#unlimited').checked;document.querySelector('#unlimited').disabled=value;",
    )
    page = page.replace(
        "ui.duration.addEventListener('change',()=>",
        "document.querySelector('#unlimited').addEventListener('change',()=>{ui.duration.disabled=document.querySelector('#unlimited').checked;ui.duration.dispatchEvent(new Event('change'));});ui.duration.addEventListener('change',()=>",
    )
    page = page.replace(
        "start();",
        "start();",
    )
    page = page.replace("</script>", """
function validatedMinutes() {
  const n = Number(document.querySelector('#duration').value);
  if (!Number.isInteger(n) || n < 1 || n > 120) throw new Error('Duration must be 1 to 120 minutes');
  return n;
}
function formatDuration(s) {
  return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
}
</script>""")
    return HTMLResponse(page)


@app.post("/session")
def start(req: StartIn):
    try:
        return {"session_id":agent.start(req.condition, req.topic, req.duration_seconds, req.internet_access), "opening": OPENINGS[req.topic], "duration_seconds":req.duration_seconds, "internet_access":req.internet_access}
    except ValueError as e:
        raise HTTPException(400,str(e))


@app.get("/transcript/{session_id}")
def transcript(session_id: str):
    try:
        return agent.transcript(session_id)
    except KeyError:
        raise HTTPException(404, "Unknown session")


@app.post("/chat")
def chat(req: ChatIn):
    try:
        return agent.reply(req.session_id,req.message)
    except KeyError:
        raise HTTPException(404,"Unknown session")
    except ValueError as e:
        raise HTTPException(400,str(e))


if __name__ == "__main__":
    # Must remain localhost-only until access control, consent, logging/data
    # retention review, and ETH infrastructure approval are implemented.
    uvicorn.run(app,host="127.0.0.1",port=8090,access_log=False)
