# Ripple Radar

An operations control tower for Wacky Wheels Co. (Hitachi Hack the Highway, TAMU Datathon 2026). A local language model reads each event message. Four agents trace its impact through a knowledge graph of the company, plan the response under the policy handbook, check the plan against all 10 rules, and execute it on the enterprise server.

Everything runs on one laptop. No cloud services, no API keys.

## Architecture

| Step | Module | Role |
|---|---|---|
| Read | `extract.py` | Qwen2.5 3B (Ollama) turns the message into JSON incidents. Code rejects any value not in the message, resolves names and dates, and retries once with the exact errors. |
| Trace | `tower/graph.py` | NetworkX knowledge graph (14 node types, 27 relations). Impact traversal and evidence paths. |
| Plan | `tower/agents.py` | Coordinator, Supply Chain Planner, Dealer and Customer Care, Quality. One shared slot ledger and loaner pool per event. |
| Check | `tower/rules.py` | The 10 handbook rules recomputed from raw tables, plus a rehearsal on a private copy of the enterprise. |
| Act | `run.py` | Sends each call to the enterprise server; stops at once if the server stops answering. Writes traces and exports. |
| View | `app.py`, `views.py`, `ui/` | The web app. |

Company data, names and dates live in `tower/world.py`. `DOCUMENTATION.md` explains the design: the pipeline, the knowledge graph and every guard against model hallucination. `CODE.md` is the map of the source: what each file and function does and how to change it safely.

## Where to run the commands

Every command below runs from **this folder**: `ripple-radar/` if you extracted the submission archive, `hitachi/` if you cloned the repository. Commands use Windows paths (`.venv/Scripts/python`); on macOS or Linux use `.venv/bin/python`.

## Prerequisites

- Python 3.12 and [Ollama](https://ollama.com). Tested on Windows 11 with an NVIDIA GPU; a CPU works, just slower.
- The organizer package, which is not included. Copy the `hack_the_highway_package` folder from the challenge into `_package/`, so that this file exists: `_package/hack_the_highway_package/data/events.json`.

## Setup

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

```bash
ollama pull qwen2.5:3b
```

Ollama serves on `http://localhost:11434`. To use another installed model, set `OLLAMA_MODEL` or pick one from the model button in the app's top bar.

## Check the install (no model needed, about a minute)

```bash
.venv/Scripts/python tests/edge.py
```

Expect `30/30 passed`.

## Run the app

Read the 15 events with the model once (about 40 seconds; writes `out/extraction.json`):

```bash
.venv/Scripts/python extract.py
```

Start the app:

```bash
.venv/Scripts/python -m uvicorn app:app --port 8050
```

Open http://localhost:8050. The app plans from the model's readings in `out/extraction.json`; if that file is missing, it reads the events with the model at startup, and it will not start without the model. It loads `submission/action_log.jsonl` so each incident shows whether its actions were accepted by the server. `USER_GUIDE.md` explains every screen.

## Execute the 15 events

1. Start a fresh enterprise server:

```bash
.venv/Scripts/python _package/hack_the_highway_package/enterprise_server.py --data _package/hack_the_highway_package/data --out runs/official --overwrite
```

2. In a second terminal, in the same folder:

```bash
.venv/Scripts/python run.py --execute http://127.0.0.1:8000 --out out/official/run
```

Output:

| Path | Contents |
|---|---|
| `runs/official/action_log.jsonl` | The server's action log; compare it with `submission/action_log.jsonl` |
| `out/official/run/traces/E-xx.json`, `E-xx.md` | One trace per event: reading, entities, graph evidence, affected records, checks, actions with graph paths, options considered and server results |
| `out/official/run/plan.json` | The full plan for all events |
| `out/official/run/ontology.json`, `ontology.mmd`, `graph.json` | Graph schema and the full graph |

Start the server fresh for every run. Its state persists per event, so a second run on the same server would be refused or would duplicate notices. If the server stops answering mid-run, `run.py` stops and names the event and call.

`run.py` always reads the events with the model and stops with a clear error if Ollama or the model is missing. For development without a model only, `--reference tests/fixtures/reference_readings.json` plans from hand-written readings and prints DEVELOPMENT MODE.

## Live demo: a new message, end to end

Start a separate demo enterprise server, with its own event feed and its own log, so it never touches the official run:

```bash
.venv/Scripts/python _package/hack_the_highway_package/enterprise_server.py --data _package/hack_the_highway_package/data --events demo/demo_events.json --out runs/demo --port 8001 --overwrite
```

In the app, click **New event**, type a message and click **Analyze event**. The model reads it; the graph, agents and RuleBook plan and check it; it is held as **Preview, not sent**. Then click **Send to enterprise server**: every action goes to the demo server, and the status follows the server's answers (Resolved, Partial or Failed). To point at another server, set `ENTERPRISE_URL` before starting the app. Restart the demo server with `--overwrite` before each demo, because event ids restart at LIVE-01 when the app restarts.

What to know about the demo feed: the enterprise server only accepts actions for event ids listed in its feed, so `demo_events.json` declares 20 placeholder slots (LIVE-01 to LIVE-20). The typed message is read, planned and checked in the app; the server records the actions under that slot, but its `/events` feed does not store the typed text. As a safety guard, the app reads the target server's feed before sending and refuses if it is serving the official events or has no slot for the id.

## Tests

```bash
.venv/Scripts/python tests/edge.py
```

30 checks on planning, names, dates, statuses and graph evidence, including that every cited path is a chain of real graph edges. No model needed.

```bash
.venv/Scripts/python audit/independent.py
```

The independent validator. Written separately from the planner and sharing no code with it, it starts from its own annotated reading of each event and recomputes every expected action from the handbook and data, then compares them with `submission/action_log.jsonl`. Results go to `audit/comparison.json`.

```bash
.venv/Scripts/python audit/readings_check.py
```

Checks reading: compares the model's readings in `submission/traces/` with the validator's annotations (15 of 15 match).

```bash
.venv/Scripts/python tests/live.py
```

End-to-end test of the live path, 14 checks (needs Ollama; about 2 minutes). It starts a demo enterprise server, a server with the official feed and two app instances, then checks that two simultaneous sends write once; empty or oversized messages are rejected; the security headers are set; a typed message is read by the model and sent; the server receives exactly the planned calls with the same arguments; a call the server rejects shows as Partial with the reason; a plan cannot be sent twice; official events cannot be sent; the app refuses a server serving the official feed; the official log is unchanged.

```bash
.venv/Scripts/python tests/stress.py --n 40 --seed 7
```

40 generated messages with known answers, read by the model and graded. Results go to `tests/out/`.

## Inspect the results

- `submission/action_log.jsonl`: one line per server call, with `event_id`, `tool`, `args` and `ok`.
- `submission/traces/E-09.md`: a readable trace. `E-09.json` holds the same trace as JSON.
- In the app: **Incidents** for one event, **Evidence** for the full log and the policy matrix, and **Download report** on any incident.

## Troubleshooting

| Problem | Fix |
|---|---|
| `FileNotFoundError` for `events.json` or `enterprise.py` | The organizer package is missing or in the wrong folder. `_package/hack_the_highway_package/data/events.json` must exist. |
| "The language model is not reachable" | Start Ollama (`ollama serve`), check `ollama list` shows `qwen2.5:3b`, and run again. |
| The model button shows **Offline** | Same as above. |
| `run.py` prints "Stopped at ... the server stopped answering" | Restart the enterprise server with `--overwrite`, then run again. Do not rerun on the same server. |
| Port 8000 or 8050 in use | Pass `--port` to the server or uvicorn, and change the `--execute` URL to match. |
| The page looks out of date after an update | Hard refresh (Ctrl+Shift+R). |

## Security

The app binds to `127.0.0.1`; keep it that way, since it has no login. `DOCUMENTATION.md` section 9 lists the protections: escaped output and a strict Content Security Policy, input limits, a lock so a plan is written once, a guard against sending to the official server, and no secrets loaded.

## Submission

`submission/README.md` lists every deliverable. The design card source is `docs/design_card.html`; print it to PDF with Edge or Chrome:

```bash
msedge --headless --no-pdf-header-footer --print-to-pdf=submission/design_card.pdf docs/design_card.html
```
