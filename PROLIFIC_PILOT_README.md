# Prolific pilot: four participants (Mac-hosted)

This is a **separate participant mode** in the existing Sycophancy Survey Agent repository. Participants use a browser over HTTPS, while Qwen3-14B and the participant app run locally on the researcher's Mac. The existing research chat (port 8090) and grading mode (8091) remain separate.

**Status:** Prototype committed to the repository. A four-person live trial has **not yet been run**. Test everything with a separate database before opening recruitment. Do not use the researcher chat URL for Prolific.

## How the experiment works

- Four distinct Prolific IDs receive four randomized slots: **2 Neutral and 2 Sycophantic**. Conditions are assigned server-side and are **never included in participant responses**.
- The topic is fixed for the pilot (AI regulation by default), the conversation lasts five minutes by default, and internet search is disabled in both conditions.
- Each user message and model answer is saved in a private SQLite file on the researcher's Mac, associated with Prolific PID, study ID, session ID, hidden condition, timestamps and topic.
- Refreshing the browser preserves the session via a browser-local token. A new browser profile does not inherit it. Re-entering an already-used PID cannot create a second session.
- Finishing shows a Prolific return link only when the official completion URL has been configured.

## Step 1: Update repository, install dependencies, and test

In Terminal A:

```bash
cd ~/Documents/eth-sycophancy-survey-agent
git pull --ff-only
source .venv/bin/activate
python -m pip install -e '.[server,dev]'
python -m pytest -q
```

If using a clean clone, follow the [main README](README.md) first for Python and MLX installation. A failing test should be investigated before recruiting.

## Step 2: Run the local model (Terminal A)

```bash
python -m mlx_lm server --model mlx-community/Qwen3-14B-4bit --port 8080
```

Leave it running. On the first run the model may need to download.

## Step 3: Start the four-person TEST pilot (Terminal B)

```bash
cd ~/Documents/eth-sycophancy-survey-agent
source .venv/bin/activate
PILOT_DB_PATH=private/prolific_TEST.sqlite python scripts/run_prolific_pilot.py
```

This is **port 8092**, not 8090. The TEST file stores mock participants and cannot contaminate production as long as the production file differs.

Open http://127.0.0.1:8092/?PROLIFIC_PID=TEST001 locally to verify the page before tunneling.

## Step 4: Expose only the participant app (Terminal C)

If your previous Cloudflare Tunnel is still running for the research chat on port 8090, stop it with Ctrl+C first. Use:

```bash
cloudflared tunnel --url http://127.0.0.1:8092
```

Copy the new `https://...trycloudflare.com` URL from the terminal. Open it in a private browser window, appending:

```text
?PROLIFIC_PID=TEST001
```

Read the consent page, start, send a message and finish. Repeat with `TEST002` in another browser profile if you want to test a second simulated participant. The TEST database accepts four different IDs total. The temporary tunnel URL will change on restart.

**Do not use the old port-8090 tunnel for real participants**: it exposes researcher controls and treatment choice. Only the new port-8092 interface hides conditions.

## Step 5: Check data privately

In another Terminal from the repo root:

```bash
python - <<'PY'
import sqlite3, json
con = sqlite3.connect('private/prolific_TEST.sqlite')
for pid, condition, finished, transcript in con.execute(
    'SELECT prolific_pid, condition, finished_at, messages_json FROM participants ORDER BY slot'
):
    print(pid, condition, 'finished' if finished else 'in progress', len(json.loads(transcript)), 'messages')
PY
```

The terminal output contains experimental ground truth. Do not share it with participants. Both databases are excluded from Git through the existing `.gitignore`.

## Step 6: Launch the four-person REAL pilot separately

Stop the TEST participant server with Ctrl+C. Qwen can continue running.

In Terminal B:

```bash
PILOT_DB_PATH=private/prolific_REAL.sqlite python scripts/run_prolific_pilot.py
```

Create a **new** tunnel to port 8092. In Prolific, create an External Study and use the new HTTPS tunnel URL. Configure Prolific to supply `PROLIFIC_PID`, `STUDY_ID` and `SESSION_ID` as URL parameters using **the exact template offered in the Prolific study editor**. Do not manually hardcode people's IDs. Configure the completion code in Prolific.

To enable the completion link, restart the REAL participant server with the **official** URL obtained from your Prolific study configuration:

```bash
PILOT_DB_PATH=private/prolific_REAL.sqlite \
PROLIFIC_COMPLETION_URL='https://app.prolific.com/submissions/complete?cc=YOUR_ACTUAL_CODE' \
python scripts/run_prolific_pilot.py
```

The code above is a template, **not a valid completion code**. Do not invite paid participants until you have tested the real return link in Prolific preview.

## Export private data

```bash
python - <<'PY'
import csv,sqlite3
from pathlib import Path
p=Path('private/prolific_REAL.sqlite')
out=Path('private/prolific_REAL_export.csv')
con=sqlite3.connect(p);con.row_factory=sqlite3.Row
rows=con.execute('SELECT prolific_pid,study_id,prolific_session_id,condition,topic,started_at,finished_at,messages_json FROM participants ORDER BY slot').fetchall()
cols=['prolific_pid','study_id','prolific_session_id','condition','topic','started_at','finished_at','messages_json']
with out.open('w',newline='',encoding='utf-8') as fh:
    writer=csv.DictWriter(fh,fieldnames=cols);writer.writeheader();writer.writerows(dict(row) for row in rows)
print('Exported',len(rows),'records to',out)
PY
```

## Limitations before real recruitment

1. **Anyone knowing the tunnel link can occupy a slot** by supplying an arbitrary PID. The code has no verified Prolific identity, admission token, rate limit or login. For a paid pilot, consider an authenticated tunnel or a vetted admission flow.
2. Your Mac must stay awake and connected. Prolific participants may experience model latency, especially when concurrent requests queue. Test simultaneous conversations and interrupted connections; this code has not been load tested.
3. The session is identified by a browser-local token. Clearing local storage or switching browsers loses the ability to resume; a PID alone cannot recover it.
4. Participants can finish after a message, even before the five-minute timer expires. Decide whether this matches the study design and payment rules.
5. The consent text is provisional; update it to match the researcher's actual ethics and data-handling commitments before recruitment.
6. Keep production SQLite and its backups outside GitHub. The experiment needs a secure data retention, backup and withdrawal plan.

For a **self-test today**, Steps 1–5 using only the TEST database and mock `TEST001` PID are sufficient. There is no need to create a Prolific study yet.
