"""Local grading interface backed by shared remote Cloudflare Worker.
No LLM server is needed to annotate an already generated dataset.
"""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(title="Sycophancy — Blind Grading")
ENDPOINT = os.environ.get("GRADING_API_URL", "").rstrip("/")

class Person(BaseModel):
    grader_id: str = Field(min_length=16, max_length=100)
    grader_name: str = Field(min_length=2,max_length=100)

class Rating(Person):
    dialogue_id: str
    score: int = Field(ge=1,le=5)

def call(path, payload=None):
    if not ENDPOINT.startswith("https://"):
        raise HTTPException(503, "Set GRADING_API_URL to the deployed HTTPS grading service.")
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(ENDPOINT+path,data=data,method="GET" if data is None else "POST",
        headers={"Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=15) as resp:
            return json.load(resp)
    except HTTPError as exc:
        msg=exc.read().decode("utf-8","replace")[:300]
        raise HTTPException(exc.code,msg)
    except (URLError,TimeoutError) as exc:
        raise HTTPException(503,str(exc))

@app.get("/")
def page():
    return HTMLResponse(Path(__file__).with_name("grading_chat.html").read_text(encoding="utf-8"))

@app.get("/progress")
def progress():
    return call("/progress")

@app.post("/next")
def next_item(person: Person):
    return call("/next",person.model_dump())

@app.post("/rate")
def rate(rating: Rating):
    return call("/rate",rating.model_dump())

if __name__=="__main__":
    uvicorn.run(app,host="127.0.0.1",port=8091,access_log=False)
