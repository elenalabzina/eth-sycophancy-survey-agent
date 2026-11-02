"""Pilot checks that never contact the local Qwen server."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
def load():
    spec=importlib.util.spec_from_file_location("pilot",ROOT/"scripts"/"run_prolific_pilot.py")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

PIDS=("000000000000000000000001","000000000000000000000002",
      "000000000000000000000003","000000000000000000000004")

def test_balanced_private_assignment_and_no_identity_leak(tmp_path,monkeypatch):
    m=load()
    x={PIDS[0]:{"group":"higher","condition":"neutral"},
       PIDS[1]:{"group":"higher","condition":"sycophantic"},
       PIDS[2]:{"group":"lower","condition":"neutral"},
       PIDS[3]:{"group":"lower","condition":"sycophantic"}}
    p=tmp_path/"assignments.json";p.write_text(json.dumps({"participants":x}))
    monkeypatch.setenv("PILOT_ASSIGNMENTS_FILE",str(p))
    monkeypatch.setenv("PILOT_DB",str(tmp_path/"pilot.db"))
    assert m.assignments()==x
    m.init_db()
    with m.connect() as db:
        db.execute("INSERT INTO pilot_sessions(pid,token,group_name,condition_name,started,baseline_stance,baseline_confidence) VALUES(?,?,?,?,?,?,?)",
                   (PIDS[0],"t"*48,"higher","neutral",m.time.time(),40,65))
        db.execute("INSERT INTO pilot_messages(pid,seq,role,content,timestamp) VALUES(?,?,?,?,?)",
                   (PIDS[0],0,"user","my view",m.time.time()))
    result=m.view(m.require_row("t"*48))
    assert result["messages"]==[{"role":"user","content":"my view"}]
    assert "condition_name" not in result and "group_name" not in result
    assert result["remaining_seconds"]<=600

def test_invalid_or_unbalanced_assignments_rejected(tmp_path,monkeypatch):
    m=load()
    p=tmp_path/"bad.json"
    p.write_text(json.dumps({"participants":{PIDS[i]:{"group":"lower","condition":"neutral"} for i in range(4)}}))
    monkeypatch.setenv("PILOT_ASSIGNMENTS_FILE",str(p))
    with pytest.raises(RuntimeError,match="2×2"):
        m.assignments()

def test_study_ui_does_not_expose_policy_names():
    s=(ROOT/"scripts"/"prolific_pilot.html").read_text()
    assert "sycophantic" not in s.casefold()
    assert "neutral" not in s.casefold()
