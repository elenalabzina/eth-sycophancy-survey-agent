"""Export the private, locally recorded Prolific pilot outcomes."""
import csv
import json
import os
import sqlite3
from pathlib import Path

db = Path(os.getenv("PILOT_DB", "outputs/prolific_pilot.sqlite"))
if not db.exists():
    raise SystemExit(f"No database found: {db}")
out = Path("outputs/prolific_pilot_export_PRIVATE.csv")
out.parent.mkdir(parents=True,exist_ok=True)
with sqlite3.connect(db) as conn, out.open("w",newline="",encoding="utf-8") as file:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM pilot_sessions ORDER BY started"
    ).fetchall()
    keys = ["pid","study_id","submission_id","group_name","condition_name","started",
            "baseline_stance","baseline_confidence","finished","post_stance",
            "post_confidence","reflection","transcript_json"]
    writer=csv.DictWriter(file,fieldnames=keys)
    writer.writeheader()
    for row in rows:
        data=dict(row)
        messages = [
            {"role":m["role"],"content":m["content"],"timestamp":m["timestamp"]}
            for m in conn.execute("SELECT role,content,timestamp FROM pilot_messages WHERE pid=? ORDER BY seq",(row["pid"],))
        ]
        writer.writerow({k:(json.dumps(messages,ensure_ascii=False) if k=="transcript_json" else data.get(k)) for k in keys})
print(f"Wrote private research export: {out}")
