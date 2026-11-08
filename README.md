# Ripple Radar

Our entry for **Hitachi: Hack the Highway** at TAMU Datathon 2026: an operations control tower for the automaker Wacky Wheels Co.

A local language model (Qwen2.5 3B via Ollama) reads each operational message. Four agents then trace its impact through a knowledge graph of the company, plan the response under the policy handbook, verify the plan against all 10 rules, and execute it on the enterprise server. Everything runs on one laptop, with no cloud services and no API keys.

| | |
|---|---|
| Submission package | [`hitachi/submission/`](hitachi/submission/README.md): action log, design card, ontology, traces, model citation, screenshots |
| Setup and reproduction | [`hitachi/README.md`](hitachi/README.md) |
| Technical documentation | [`hitachi/DOCUMENTATION.md`](hitachi/DOCUMENTATION.md): pipeline, knowledge graph, hallucination guards, data |
| Code reference | [`hitachi/CODE.md`](hitachi/CODE.md): every module, the path of one message through the code, how to change it safely |
| User guide | [`hitachi/USER_GUIDE.md`](hitachi/USER_GUIDE.md) |
| Independent audit | [`hitachi/AUDIT_REPORT.md`](hitachi/AUDIT_REPORT.md) |

## Quick start

Requires Python 3.12, [Ollama](https://ollama.com), and the organizer package at `hitachi/_package/hack_the_highway_package/`. Windows paths shown; on macOS or Linux use `.venv/bin/python`.

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r hitachi/requirements.txt
```

```bash
ollama pull qwen2.5:3b
```

```bash
cd hitachi && ../.venv/Scripts/python extract.py && ../.venv/Scripts/python -m uvicorn app:app --port 8050
```

Open http://localhost:8050. To execute the 15 events against the enterprise server, follow [`hitachi/README.md`](hitachi/README.md).

## Repository

```
hitachi/              Ripple Radar: app, agents, knowledge graph, tests, docs
hitachi/submission/   Judge-facing package
```

The organizer package is not included. Download it from the challenge page into `hitachi/_package/`.
