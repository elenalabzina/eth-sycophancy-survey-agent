# Blind grading mode — local setup and shared progress

This is a **second mode** of the same Sycophancy Survey Agent repository. It runs locally on each reviewer's computer but uses one shared **Cloudflare Worker + D1** database for ratings and progress. Unlike chat mode, it does **not** require each reviewer to run Qwen. Qwen is needed **once**, by the researcher, to generate the dataset.

> **Status:** Development prototype. The code is committed, but shared storage will not work until the project owner creates and deploys the D1 database and Worker. No grading dataset is included in the public repository, and no scores currently exist.

## The workflow

1. Researcher starts Qwen locally and generates **100 conversations** in a private JSON file.
2. Each conversation contains exactly **3 simulated-user messages and 2 target-assistant answers**, alternating. Another model agent writes the user messages, without being told the assigned treatment.
3. Experimental conditions are balanced: 50 Neutral and 50 Sycophantic; topics are balanced too. Metadata includes ground truth, model, and policy version.
4. Researcher uploads the generated dataset to a shared Cloudflare D1 database **once** using an admin token.
5. Reviewers clone/pull this GitHub repository and run a separate local grading page on **http://127.0.0.1:8091**. They enter a name and see the earliest dialogue with fewer than two scores that they have not already graded.
6. Server saves each score, grader name, browser-generated reviewer ID, dialogue ID and timestamp. Ratings are deduplicated by reviewer ID; the shared progress indicator counts a dialogue as complete after **two distinct reviewers** have graded it.
7. Ground truth is **never sent to the reviewer interface**. Only an admin export joins hidden condition labels with scores.

Note: A browser-generated ID is not a secure identity. Clearing local storage or changing browsers creates a new ID. Suitable for a small trusted pilot, **not** a fraud-resistant participant study. The server can assign the same unfinished dialogue to two browsers simultaneously, but accepts at most two scores; a late third submission is rejected and another dialogue is offered.

## A. Researcher: generate dialogues locally

From the repository root, while the Qwen server is running on port 8080:

```bash
git pull
source .venv/bin/activate
python scripts/generate_grading_dialogues.py --count 100
```

The generated private file is `outputs/grading/dialogues_PRIVATE.json`. Generation requires approximately 500 model completions (3 simulated-user turns + 2 agent turns for each dialogue). **Do not commit this file**, because it includes the hidden condition labels. The generator refuses to overwrite an existing dataset.

## B. Researcher: create shared Cloudflare storage (one-time setup)

Requires a Cloudflare account with Workers/D1 enabled and Node.js with `npx` installed. The shared service uses [Cloudflare Workers](https://developers.cloudflare.com/workers/) and [D1](https://developers.cloudflare.com/d1/). From the repo root:

```bash
cd grading/cloudflare
npx wrangler login
npx wrangler d1 create sycophancy-grading
```

Copy the returned `database_id` into `grading/cloudflare/wrangler.toml` (replace `REPLACE_WITH_YOUR_D1_DATABASE_ID`). Do not put credentials in the file.

```bash
npx wrangler d1 execute sycophancy-grading --remote --file=schema.sql
npx wrangler secret put ADMIN_TOKEN
npx wrangler deploy
```

Choose a **long random admin token**, store it securely, and keep it out of GitHub. Wrangler prints a Worker HTTPS URL, such as `https://your-worker.your-subdomain.workers.dev`. **Use your actual URL.**

### Upload the dataset

Return to repository root (from `grading/cloudflare`, use `cd ../..`). Set your actual Worker URL and admin token in your current terminal:

```bash
export GRADING_API_URL="https://YOUR_WORKER_URL"
read -s ADMIN_TOKEN
export ADMIN_TOKEN
curl -fS -X POST "$GRADING_API_URL/admin/import" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @outputs/grading/dialogues_PRIVATE.json
unset ADMIN_TOKEN
```

The import accepts **exactly 100 items**, is intentionally one-time, and refuses to overwrite an initialized dataset or previous ratings. This prevents accidental resets while people are annotating.

### Export your data (researcher only)

```bash
read -s ADMIN_TOKEN
curl -fS "$GRADING_API_URL/admin/export" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -o outputs/grading/ratings_PRIVATE.json
unset ADMIN_TOKEN
```

Export includes dialogue text, hidden condition labels, reviewer names, reviewer IDs, grades and timestamps. **Keep this export private.** If needed, transform it into CSV offline.

## C. Reviewer: grade conversations on your own machine

No Qwen model, MLX, GPU, or Docker is needed for grading an already generated dataset. Clone the same repository (or `git pull` if already cloned):

```bash
git clone https://github.com/elenalabzina/eth-sycophancy-survey-agent.git
cd eth-sycophancy-survey-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[server]'
```

The study organizer must give you the **public Worker HTTPS URL** (not the private admin token). In the same Terminal, run:

```bash
export GRADING_API_URL="https://YOUR_WORKER_URL"
python scripts/run_grading_server.py
```

Open **http://127.0.0.1:8091/**. Enter your name, select **Start grading**, review the transcript and score the assistant on a 1–5 scale. After **Save rating and continue**, the next eligible dialogue appears automatically. The progress bar reflects all reviewers' submissions, not just your machine.

To stop: press `Ctrl+C` in the grading-server terminal.

## Chat mode remains unchanged

The existing chat mode and its [main README](README.md) still work on `http://127.0.0.1:8090/`. Grading mode runs separately on port `8091`. Running both modes does not interfere with the stored shared ratings.

## Privacy and limitations

This setup is for a small trusted group of reviewers. It has **no verified login, informed consent workflow, or rate limiting**. Names and grades are stored in an online database. Only participants who agree to that use should enter their names. Keep the Worker URL within the reviewer group and protect the admin token. Before broader deployment, implement authenticated evaluator identities, server-side abuse protection, consent and appropriate data retention.
