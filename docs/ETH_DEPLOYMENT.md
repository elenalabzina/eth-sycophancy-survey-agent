# ETH deployment, Qualtrics integration, and validation

This is an engineering guide, **not** a claim of fielding readiness. The local server is bound to `127.0.0.1:8090`, unauthenticated, and stores sessions only in memory.

## Deployment outline

1. Provision an ETH-approved GPU inference endpoint with an OpenAI-compatible API (for example, vLLM). Configure `SURVEY_MODEL_CONFIG` with model ID and endpoint. Keep the same inference backend, model revision, sampling parameters and tools across experimental arms.
2. Serve FastAPI behind an ETH-approved HTTPS reverse proxy, with authentication, rate limits, access controls, durable approved storage, audit/retention policies, and consent/privacy review. **Do not expose the local development API directly to the internet.**
3. For an experimental Qualtrics build, embed a participant-facing chat view (for example via a hosted iframe if allowed by Qualtrics settings). Remove preview controls revealing `neutral`/`sycophantic` and optional researcher configuration.
4. Assign experimental conditions server-side (or securely transmit the assigned condition from Qualtrics without giving the participant control). Record a pseudonymous Qualtrics ResponseID ↔ session_id mapping in approved storage.
5. Store full transcripts server-side. In Qualtrics Embedded Data save a transcript reference/session ID and condition, rather than relying on unlimited JSON storage. Ensure completion, timeout, reconnection, refresh, and partial response handling are tested.
6. Restrict internet retrieval consistently across arms; SearXNG forwards queries to external providers and must not receive participant-identifying information.

## Current local API

- `POST /session`: `{"topic":"ai","condition":"neutral","duration_seconds":300,"internet_access":false}` → `session_id`, `opening`, duration.
- `POST /chat`: `{"session_id":"...","message":"..."}` → reply, sources, turn, remaining_seconds.
- `GET /transcript/{session_id}`: messages, condition, topic, duration and internet flag.
- `GET /docs`: FastAPI development API reference.

If `condition` is omitted, the local service assigns a random condition. Production assignment should be coordinated with the survey experiment and securely logged. The current prototype is **not yet integrated with Qualtrics**.

## Validate after moving to ETH hardware

1. Freeze and record Git SHA, policy version, model revision/quantization, serving backend, inference settings, search setting.
2. Run `python -m pytest -q`, then test both treatments × both topics, all timer modes, source handling, latency/error behavior, transcript export and storage, and end-to-end survey flow.
3. Generate **new** matched, blinded A/B samples on the actual ETH inference service. Do not reuse previously graded Mac outputs to claim independent validation. The development calibration generator is deliberately kept in the private research repository.
4. Blind raters to condition assignments. Assess *evaluative affirmation*, *epistemic accommodation*, *framing alignment*, *overall sycophancy* (−2 A more, +2 B more), confidence, factual errors, length, and repetitive praise.
5. Lock scores before unblinding; orient ratings so a positive score means the assigned Sycophantic arm is more accommodating. Report directions, zeros, opposite-direction items, error rates and variation between topics. Short pilot results are descriptive, not confirmatory evidence.
6. Repeat matched full conversations to assess pressure, factual correction, and multi-turn stability. Revalidate any modified policy or model before deploying to participants.

**Participant recruitment requires separate ethics, data protection, security, reliability and experimental validation sign-off.**
