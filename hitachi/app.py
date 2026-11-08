"""Web controller: loads the plans at startup and serves the API and UI. Endpoints validate input and delegate."""
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import extract
import views
from run import execute
from tower.agents import Coordinator
from tower.graph import KnowledgeGraph
from tower.rules import RuleBook
from tower.types import Status
from tower.world import DATA, DateResolver, World

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "ui")
READINGS = os.path.join(HERE, "out", "extraction.json")
OFFICIAL_LOG = os.path.join(HERE, "submission", "action_log.jsonl")
DEMO_SERVER = os.environ.get("ENTERPRISE_URL", "http://127.0.0.1:8001")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MAX_PREVIEWS = 50
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                               "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
                               "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
log = logging.getLogger("ripple-radar")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_readings(world, dates, events):
    """The model's readings of the 15 events; read them now if they were never cached."""
    if os.path.exists(READINGS):
        return load_json(READINGS)
    extract.require_model()
    log.warning("Reading the 15 events with the model (about 40 seconds, once).")
    readings = {e["event_id"]: extract.extract_event(world, dates, e, extract.providers()) for e in events}
    os.makedirs(os.path.dirname(READINGS), exist_ok=True)
    with open(READINGS, "w", encoding="utf-8") as f:
        json.dump(readings, f, indent=2)
    return readings


def load_official_log():
    rows = {}
    if os.path.exists(OFFICIAL_LOG):
        with open(OFFICIAL_LOG, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    rows.setdefault(row["event_id"], []).append(row)
    return rows


world, dates = World(), DateResolver()
kg = KnowledgeGraph(world)
tower, rules = Coordinator(world, kg, dates), RuleBook(world)
presenter = views.Presenter(world, kg)
events = load_json(os.path.join(DATA, "events.json"))
official_ids = {e["event_id"] for e in events}
official_rows = load_official_log()
plans = {}
lock = threading.Lock()
previews = 0


def plan_event(event, reading):
    """Plans one event, checks it against the handbook and matches it to the official server log."""
    start = time.perf_counter()
    plan = tower.handle(event, reading["incidents"])
    plan["checks"] = rules.check(plan)
    plan["rehearsal_failed"] = rules.last_failed
    plan["execution"] = views.match_log(plan, official_rows.get(plan["event_id"]))
    plan["read_by"] = {k: reading.get(k) for k in ("handled_by", "model", "attempts")}
    plan["ms"] = round((time.perf_counter() - start) * 1000)
    return plan


readings = load_readings(world, dates, events)
for e in events:
    plans[e["event_id"]] = plan_event(e, readings[e["event_id"]])

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if request.url.path.startswith("/static/") and not request.url.path.startswith("/static/vendor/"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/static", StaticFiles(directory=UI), name="static")


def known_plan(eid):
    if eid not in plans:
        raise HTTPException(404, "Unknown incident.")
    return plans[eid]


@app.get("/")
def index():
    return FileResponse(os.path.join(UI, "index.html"))


@app.get("/api/overview")
def overview():
    return presenter.overview(plans)


@app.get("/api/event/{event_id}")
def event(event_id: str):
    return presenter.detail(known_plan(event_id))


@app.get("/api/why/{name:path}")
def why(name: str):
    node = presenter.find(name[:120])
    if node is None:
        raise HTTPException(404, "No record by that name.")
    return presenter.why(node)


@app.get("/api/places")
def places():
    def pick(rows, *keys):
        return {k: {f: r[f] for f in keys} for k, r in rows.items()}
    return {"plants": pick(world.plants, "name", "city"), "suppliers": pick(world.suppliers, "name", "city"),
            "dealers": pick(world.dealers, "name", "city")}


def installed_models():
    """Models installed in Ollama, or None when it is not reachable."""
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=1.5) as r:
            return [{"name": m["name"], "gb": round(m.get("size", 0) / 1e9, 1)} for m in json.loads(r.read()).get("models", [])]
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        return None


@app.get("/api/health")
def health():
    model, models = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b"), installed_models()
    return {"model": model, "online": bool(models) and any(m["name"] == model for m in models), "models": models or []}


class ModelChoice(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@app.post("/api/model")
def choose_model(body: ModelChoice):
    # Only a model already installed in Ollama can be selected.
    if not any(m["name"] == body.name for m in installed_models() or []):
        raise HTTPException(400, "That model is not installed on this computer.")
    os.environ["OLLAMA_MODEL"] = body.name
    return health()


@app.get("/api/board")
def board():
    return presenter.board(plans)


@app.get("/api/audit")
def audit():
    return presenter.audit(plans)


@app.get("/api/search")
def search(q: str = Query("", max_length=60)):
    return presenter.search(q)


@app.get("/api/node/{nid:path}")
def node(nid: str):
    if nid not in kg.g:
        raise HTTPException(404, "No record by that name.")
    return presenter.node(nid)


@app.get("/api/report/{eid}")
def report(eid: str):
    plan = known_plan(eid)
    disposition = f'attachment; filename="{plan["event_id"]}-report.md"'
    return PlainTextResponse(presenter.report(plan), headers={"Content-Disposition": disposition})


class NewEvent(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source: str = Field("simulated", max_length=40)


@app.post("/api/simulate")
def simulate(body: NewEvent):
    """Reads, plans and checks a new message. It is held as a preview; nothing is sent."""
    global previews
    with lock:
        if previews >= MAX_PREVIEWS:
            raise HTTPException(429, "Too many previews. Restart the app to clear them.")
        previews += 1
        eid = f"LIVE-{previews:02d}"
    ev = {"event_id": eid, "source": body.source, "text": body.text, "received_at": time.strftime("2027-03-08T%H:%M:00")}
    try:
        plan = plan_event(ev, extract.extract_event(world, dates, ev, extract.providers()))
    except Exception:
        log.exception("Planning %s failed", eid)
        raise HTTPException(500, "The message could not be analyzed.")
    with lock:
        plans[eid] = plan
    return presenter.detail(plan)


def demo_feed():
    """Event ids the demo server accepts; raises when no server answers."""
    try:
        with urllib.request.urlopen(DEMO_SERVER.rstrip("/") + "/events", timeout=3) as r:
            return {e["event_id"] for e in json.loads(r.read())}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError):
        raise HTTPException(503, f"No enterprise server at {DEMO_SERVER}. Start the demo server (see README).")


@app.post("/api/execute/{eid}")
def execute_live(eid: str):
    """Sends a checked preview to the demo enterprise server, once."""
    if not eid.startswith("LIVE-"):
        raise HTTPException(400, "The 15 official events were executed by run.py; only new events are sent from here.")
    # One send at a time, so two clicks can never write the same plan twice.
    with lock:
        plan = known_plan(eid)
        if plan.get("execution"):
            raise HTTPException(409, "This plan was already sent.")
        if not plan["actions"] or views.status(plan) not in (Status.VERIFIED, Status.REVIEW):
            raise HTTPException(400, "Only a plan that passed every check can be sent.")
        feed = demo_feed()
        if feed & official_ids:
            raise HTTPException(403, f"{DEMO_SERVER} is serving the official event feed. New events are only sent to a demo server.")
        if eid not in feed:
            raise HTTPException(400, f"The demo server has no slot for {eid}. Restart it with --events demo/demo_events.json --overwrite.")
        sent = dict(plan)
        execute(DEMO_SERVER, sent)
        plan["execution"] = views.record_results(plan, DEMO_SERVER, eid, sent.get("stopped"))
    return presenter.detail(plan)
