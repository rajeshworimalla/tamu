# Code reference

This is the map of the source: what each file does, which function to open for a given question, and how to change things without breaking the official run. `DOCUMENTATION.md` explains the design; this file explains the code.

About 2,300 lines of Python (without tests) and 1,400 of JavaScript. No framework beyond FastAPI on the server and no build step on the client.

## One message, start to finish

Following E-09 ("Orbit: the surround-view cameras run for Huntsville can't make it Monday Mar 29...") through the code:

1. `extract.extract_event` sends the text to the model through `ask_ollama`. The request uses a JSON schema and temperature 0, so the reply is always the same shape.
2. `extract.clean` throws away placeholder values and any shipment or lot id the message never mentions. `extract.validate` then runs the checks: every value must be in the text (`grounded`), the incident kind must match the wording (`scope` with `CUES`), digest items can't be mixed (`together`), and the names and dates must resolve (`tower.world.resolve_incident`). If anything fails, the model gets one retry with the exact errors. If the retry also fails, the message goes to review.
3. `extract.settle` replaces the model's free-text reason for noise or a rumor with one written by code (`explain`).
4. `tower.agents.Coordinator.handle` takes the resolved reading. It runs `KnowledgeGraph.fact_check` first; a reading whose relationships aren't edges in the graph stops there.
5. `SupplyChainPlanner.plan` asks the graph for the affected builds (`KnowledgeGraph.delay_impact`), then places each one through `Ledger.place`, which returns a `Placement`. `Ledger.options` records what else was considered.
6. `CustomerCare.plan` groups the waiting customer orders by dealer and ranks loaners. `QualityAgent.plan` handles lots when there are any.
7. `KnowledgeGraph.evidence` writes the per-incident path the challenge asks for, and `Coordinator.finish` records every action as a node in the graph.
8. `tower.rules.RuleBook.check` recomputes the ten handbook rules from the raw tables and rehearses every call on a private copy of the enterprise. `run.guard` turns a failed plan into a single escalation.
9. `run.execute` posts each call to the enterprise server and stops at the first one that gets no answer.
10. `run.trace` and `run.record` write the Markdown and JSON traces.

The web app does steps 1 to 8 in `app.plan_event`, and only reaches step 9 when someone presses Send on a preview.

## Layers

| Layer | Files | Rule |
|---|---|---|
| Controller | `app.py` | Validates input, holds the lock, delegates. No business logic. |
| Presentation | `views.py` | Shapes plans into API responses. No file or network access. |
| Domain | `tower/agents.py`, `tower/graph.py`, `tower/rules.py` | Planning, traversal and policy. No web code. |
| Data | `tower/world.py` | Reads the organizer CSVs once; read-only afterwards. |
| Types | `tower/types.py` | Enums and small records shared by all of the above. |
| Model I/O | `extract.py` | The only module that talks to the language model. |
| Batch | `run.py` | Command line: read, plan, check, execute, write traces. |

Calls go downward only. `views.py` imports `run.trace` to build reports, and that is the one sideways import.

## tower/types.py

The fixed value sets, written as `StrEnum` so they compare equal to plain strings and serialize as them. That is why the logs and traces didn't change when the enums were introduced.

- `Kind`: supplier_delay, plant_outage, quality_hold, noise, unconfirmed.
- `Tool`: the eight enterprise tools, for example `Tool.TRANSFER == "mes.transfer"`.
- `Tier`, `Status`: customer tier, and the incident status shown in the app.
- `Placement(tool, plant, idx, why)`: where one build goes. `tool` is `None` when no plant has room.
- `Downstream(customer_order, dealer, customer)`: one order waiting on a build.

## tower/world.py

Loads the 16 CSVs into dicts keyed by id (`world.pos`, `world.cos`, `world.vehicles`, `world.lots` and so on). Every production order gets an `idx`, the working-day index where 0 is Monday 2027-03-08 and 19 is Friday 2027-04-02.

`World.resolve(etype, mention)` is the name lookup. It tries, in order: the id itself, an alias from `aliases.csv`, the exact catalog name, a catalog name that contains the mention, and finally a single known name or alias that appears inside the mention ("Cobalt 17-inch alloy wheel"). No match is an error, and so is more than one.

`DateResolver.resolve` handles ISO dates, "today" and "tomorrow", "this/next/last Friday", a bare weekday, "Mar 22" with or without a weekday, ordinals and "3/22". "next X" means X in the following calendar week. A weekday that disagrees with the date ("Monday, Mar 23") is an error rather than a guess.

`resolve_incident` turns one reading into real records. For a delay it finds the single shipment matching plant, part and original ETA. For an outage it turns the dates into a working-day range. For a quality hold it finds the lot. Anything that doesn't fit raises `ValueError`, which `extract.validate` reports back to the model.

## tower/graph.py

`KnowledgeGraph.__init__` builds the whole graph in one pass over `World`. The one derived relation is `Lot installed_in ProductionOrder`, computed from the lot's plant, its build window and the bill of materials.

The four traversals return `(record, path)` pairs:

- `delay_impact(shipment, from, to)`: Shipment, Part, the Models that contain it and that the plant builds, then the builds in the gap.
- `outage_impact(plant, from, to)`: builds scheduled at the plant in the window.
- `orders_downstream(po)`: `Downstream` records for a build.
- `lot_impact(lot)`: vehicles built with the lot, split by sold and unsold.

`one(node, rel)` raises when a relation that should be unique isn't, so a data problem surfaces instead of being guessed around.

`fact_check(r)` and `evidence(r)` are the per-incident checks and evidence blocks described in `DOCUMENTATION.md` section 3.6. `record`, `add_event` and `why` handle provenance: every action becomes a node, and `why(node)` answers "what was done to this record".

## tower/agents.py

`Ledger` is created fresh for every event, so events never affect each other. It holds the slot count for every plant and day, plus the disruption windows (`blocks`). Because both incidents of a compound event share the same ledger, a build can't be moved twice or into a slot another move just took.

`Ledger.place` is handbook rule 3: the earliest free day at the same plant on or after the disruption ends, otherwise the earliest free day at another plant that builds the model. Transfers look at days after the disruption first. This is the interpretation choice documented in the submission README, and the comment on that loop says so.

`SupplyChainPlanner.plan` sorts the affected builds by original date, then id, before placing them. That keeps the result deterministic.

`CustomerCare.plan` sends one `dealer.notify` per dealer with every affected order of that dealer. Loaners go to Platinum, then Gold, ranked by promised date, then order id, and stop when the dealer's pool runs out. Customers who missed out are kept in `loaners_denied` so the app can show them.

`Coordinator.handle` runs the whole thing. Rumors become one escalation. Noise becomes no actions at all. A message that mixes a real incident with a rumor gets both: the actions for the incident and one escalation for the rumor.

## tower/rules.py

`RuleBook.check` recomputes each rule's expected result straight from the tables (it never calls the graph or the planner) and compares it with the plan. `rehearse` loads the organizer's own `Enterprise` class and plays every call against a private copy, so any call the server would refuse is caught before anything is sent. `last_failed` keeps the refusals for the app.

## extract.py

`SYSTEM` is the prompt, with three worked examples. Don't run search-and-replace over this file without excluding the prompt, because its examples contain literal JSON.

`require_model` stops the program with a readable message when Ollama or the model is missing. `run.py` and the app both call it, so neither can quietly fall back to anything else.

`check` and `fingerprint` exist for one job: comparing the model's readings with `tests/fixtures/reference_readings.json` (`python extract.py --check`).

## run.py

`main` reads all 15 events with the model, plans and checks each one, executes if `--execute URL` is given, and writes `out/<run>/traces`, `plan.json`, `ontology.json`, `ontology.mmd` and `graph.json`. `--reference FILE` skips the model for development and prints DEVELOPMENT MODE.

`execute` never retries. If the server stops answering it marks the call as uncertain, marks the rest as not sent, sets `plan["stopped"]` and returns, and `main` stops the run.

## app.py and views.py

`app.py` builds everything at import time: world, graph, coordinator, rulebook, presenter. It then plans the 15 events from `out/extraction.json` (reading them with the model if that file is missing) and matches each plan against `submission/action_log.jsonl` through `views.match_log`.

Endpoints:

| Route | What it returns |
|---|---|
| `GET /api/overview` | Every event summary plus totals, for Operations |
| `GET /api/event/{id}` | Everything for the Incidents page |
| `GET /api/board`, `/api/audit` | Analytics and Evidence pages |
| `GET /api/search?q=`, `/api/node/{id}`, `/api/why/{name}` | Supply network explorer |
| `GET /api/report/{id}` | Markdown report download |
| `GET /api/health`, `POST /api/model` | Model status and switching (installed models only) |
| `POST /api/simulate` | Read, plan and check a new message; held as a preview |
| `POST /api/execute/{id}` | Send a checked preview to the demo server, once |

`views.status` is the only place a status is decided. It returns Resolved only when every action was accepted, and never reports success just because a plan exists.

`views.Presenter` builds the larger responses: `ripple` (the layered graph for the Graph tab, grouping big layers), `geo` (map data), `detail`, `overview`, `board`, `node` and `report`.

## The UI (`ui/`)

Plain ES modules, loaded by `index.html`; there are no inline scripts, so the Content Security Policy can be strict. `core.js` has the shared pieces: `api`, `esc` (HTML escaping, used for every server string), `highlight` (marks the words the model read), icons, status labels and the rule texts.

| File | Page or part |
|---|---|
| `main.js` | Router, sidebar, model switcher, the New event dialog |
| `ops.js` | Operations: KPIs, impact hub, incident list |
| `tower.js` | Incidents: queue, message, map, graph, timeline, actions, decision details, Send |
| `usmap.js`, `flow.js`, `timeline.js` | The impact map (d3), the graph view (cytoscape), the recovery timeline |
| `explorer.js` | Supply network record explorer |
| `board.js`, `audit.js` | Analytics and Evidence |
| `play.js`, `help.js`, `tour.js` | Simulation, Help, first-visit tour |

Vendored libraries live in `ui/vendor` with fixed versions: d3 7.9.0, topojson-client 3.1.0, cytoscape 3.30.2.

## Tests and audits

| File | What it proves | Needs the model |
|---|---|---|
| `tests/edge.py` | 30 checks: dates, names, loaner exhaustion, shared plants, impossible recovery, statuses, graph paths are real edges | No |
| `tests/live.py` | 14 checks against real servers: live send, exact arguments, rejected call, double click, input limits, headers, official-server guard | Yes |
| `tests/stress.py` | Generated messages with known answers, graded | Yes |
| `audit/independent.py` | Expected actions rebuilt separately from the handbook and data, compared with the log | No |
| `audit/readings_check.py` | Model readings in the traces compared with the validator's annotations | No |

## Changing things safely

After any change to `tower/` or `extract.py`, run `tests/edge.py`, then check that a fresh `run.py` still produces the official 768 calls:

```bash
.venv/Scripts/python run.py --out out/check
```

Compare `out/check/plan.json` with `submission/action_log.jsonl`, or run the full replay in the README against a fresh server. Never edit `submission/action_log.jsonl` by hand.

Some common changes:

- A new nickname: add it to `aliases.csv` in the organizer data if you own it. Otherwise extend `World.resolve`, and add a case to `tests/edge.py`.
- A new date format: extend `DateResolver.resolve`, keeping the rule that a contradiction raises, and add the wording to the date cases in `tests/edge.py`.
- A new rule: add the check to `RuleBook.check`, computed from the tables rather than from the plan, and give it a test that fails without it.
- A new tool: add it to `Tool`, plan it in the agent that owns it, and teach `RuleBook` what "correct" looks like for it.
