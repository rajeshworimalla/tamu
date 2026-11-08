import os
import sys
from collections import Counter
from datetime import date

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extract import validate
from tower.agents import Coordinator
from tower.graph import KnowledgeGraph
from tower.rules import RuleBook
from tower.types import TIER_RANK
from tower.world import DateResolver, World, date_to_idx

w, dates = World(), DateResolver()
kg = KnowledgeGraph(w)
tower, rules = Coordinator(w, kg, dates), RuleBook(w)
results = []


def case(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def invariants(plan):
    problems = []
    moved = {}
    affected = {po for r in plan["incidents"] for po in r.get("affected_production_orders", [])}
    for a in plan["actions"]:
        g = a["args"]
        if a["tool"] in ("mes.reschedule", "mes.transfer"):
            po = g["production_order_id"]
            if po in moved:
                problems.append(f"{po} moved twice")
            if po not in affected:
                problems.append(f"{po} moved but not affected")
            moved[po] = (g.get("to_plant_id", w.pos[po]["plant_id"]), date_to_idx(date.fromisoformat(g["new_date"])))
    load = Counter((o["plant_id"], o["idx"]) for po, o in w.pos.items() if o["idx"] >= 0 and po not in moved)
    load.update(moved.values())
    problems += [f"{k} over capacity" for k, n in load.items() if n > w.plants[k[0]]["slots"]]
    dealers = Counter(a["args"]["dealer_id"] for a in plan["actions"] if a["tool"] == "dealer.notify")
    problems += [f"{d} notified {n} times" for d, n in dealers.items() if n > 1]
    used = Counter(w.cos[a["args"]["customer_order_id"]]["dealer_id"] for a in plan["actions"]
                   if a["tool"] == "crm.assign_loaner")
    problems += [f"{d} loaners {n} > pool" for d, n in used.items() if n > w.loaners.get(d, 0)]
    notified = {c for a in plan["actions"] if a["tool"] == "dealer.notify" for c in a["args"]["customer_order_ids"]}
    granted = {a["args"]["customer_order_id"] for a in plan["actions"] if a["tool"] == "crm.assign_loaner"}
    for d in {w.cos[c]["dealer_id"] for c in notified}:
        queue = sorted((TIER_RANK[w.customers[w.cos[c]["customer_id"]]["tier"]], w.cos[c]["promised_date"], c)
                       for c in notified if w.cos[c]["dealer_id"] == d
                       and w.customers[w.cos[c]["customer_id"]]["tier"] != "Standard")
        want = {c for _, _, c in queue[:w.loaners.get(d, 0)]}
        if want != {c for c in granted if w.cos[c]["dealer_id"] == d}:
            problems.append(f"{d} loaner priority wrong")
    return problems


def run(eid, incidents):
    plan = tower.handle({"event_id": eid, "text": "synthetic"}, incidents)
    checks = rules.check(plan)
    return plan, [c for c in checks if not c["ok"]], rules.last_failed


plan, bad, failed = run("T-01", [{"kind": "plant_outage", "plant": "San Antonio", "start": "2027-03-15", "end": "2027-03-31"}])
denied = len(plan["loaners_denied"])
case("loaner exhaustion: whole-window outage, pools never over-allocated, priority respected",
     not invariants(plan) and not bad and not failed and denied > 0,
     f"{invariants(plan)[:3]} {bad[:2]} {failed[:2]} denied={denied}")
case("full outage forces transfers and every one lands at a plant that builds the model",
     plan["action_counts"].get("mes.transfer", 0) > 0 and all(
         w.pos[a["args"]["production_order_id"]]["model"] in w.plants[a["args"]["to_plant_id"]]["models"]
         for a in plan["actions"] if a["tool"] == "mes.transfer"))

plan, bad, failed = run("T-06", [{"kind": "plant_outage", "plant": p, "start": "2027-03-08", "end": "2027-04-02"}
                                 for p in ("Princeton", "Greensboro")])
esc = [a for a in plan["actions"] if a["tool"] == "escalate"]
case("impossible recovery: no slot invented, the build is escalated with every plant's reason, and the plan is blocked",
     esc and bad and all(a["alternatives"] and not any(x.get("chosen") for x in a["alternatives"]) for a in esc)
     and "No policy-compliant slot" in esc[0]["args"]["reason"])
case("every move records the options it rejected and the one it chose",
     all(any(x.get("chosen") for x in a["alternatives"]) for a in plan["actions"] if a["tool"] in ("mes.reschedule", "mes.transfer")))

ship = next(s for s in w.shipments.values() if s["plant_id"] == "P_IN" and s["eta_date"] == "2027-03-15")
inc = [{"kind": "plant_outage", "plant": "Princeton", "start": "2027-03-15", "end": "2027-03-17"},
       {"kind": "supplier_delay", "plant": "Princeton", "part": ship["part_id"], "original_eta": "2027-03-15",
        "new_eta": "2027-03-19"}]
plan, bad, failed = run("T-02", inc)
case("compound on one plant: no order moved twice, no slot overbooked, one notice per dealer",
     not invariants(plan) and not bad and not failed, f"{invariants(plan)[:3]} {bad[:2]} {failed[:2]}")

first = [(a["tool"], a["args"]) for a in run("T-03", inc)[0]["actions"]]
again = [(a["tool"], a["args"]) for a in run("T-03", inc)[0]["actions"]]
case("same event handled twice gives the identical plan (no state leaks between runs)", first == again)
dup = []
for _ in range(2):
    for t, g in first:
        try:
            rules.ent.call("T-dup", t, g)
        except rules.tool_error as e:
            dup.append(str(e))
case("replaying an event on a server that already ran it: moves are refused, not double-applied",
     any("already" in f for f in dup), dup[:3])

lot = next(l for l in w.lots.values() if {v["status"] for v in w.vehicles.values() if v["plant_id"] == l["plant_id"]
                                           and l["first_build_date"] <= v["build_date"] <= l["last_build_date"]} >= {"sold", "in_stock"})
plan, bad, failed = run("T-04", [{"kind": "quality_hold", "plant": lot["plant_id"], "part": lot["part_id"], "lot_id": lot["lot_id"]}])
stopped = {v for a in plan["actions"] if a["tool"] == "dealer.stop_sale" for v in a["args"]["vins"]}
owners = {a["args"]["customer_id"] for a in plan["actions"] if a["tool"] == "crm.notify_customer"}
case("quality lot with sold and unsold vehicles: stop-sale only in_stock, contact only owners",
     stopped and owners and all(w.vehicles[v]["status"] == "in_stock" for v in stopped)
     and owners == {v["customer_id"] for v in w.vehicles.values() if v["status"] == "sold" and v["plant_id"] == lot["plant_id"]
                    and lot["first_build_date"] <= v["build_date"] <= lot["last_build_date"]
                    and lot["part_id"] in w.bom[v["model"]]} and not bad and not failed)

case("ambiguous plant name is refused, never guessed", raises(lambda: w.resolve("plant", "Wacky Wheels")))
case("delay whose ETA matches no shipment is refused",
     raises(lambda: run("T-05", [{"kind": "supplier_delay", "plant": "Princeton", "part": ship["part_id"],
                                  "original_eta": "2027-03-16", "new_eta": "2027-03-19"}])))
for text, want in (("Cobalt 17-inch alloy wheel", "WHEEL-17"), ("Orbit 12-inch display", "DISPLAY-12"),
                   ("17-inch rims", "WHEEL-17"), ("WHEEL-17", "WHEEL-17")):
    case(f"part named {text!r} resolves to {want}", w.resolve("part", text)[0] == want)
case("conflicting weekday and date is refused", raises(lambda: dates.resolve("Monday, Mar 23")))
for text, want in (("Wednesday", "2027-03-10"), ("next Wednesday", "2027-03-17"), ("last Thursday", "2027-03-04"),
                   ("Monday, March 22", "2027-03-22"), ("March 22nd", "2027-03-22"), ("3/22", "2027-03-22"),
                   ("on Friday", "2027-03-12")):
    case(f"date wording {text!r} resolves to {want}", dates.resolve(text)[0].isoformat() == want)
case("missing required fields are caught before acting",
     any("missing" in e for e in validate(w, dates, [{"kind": "plant_outage", "plant": "Princeton"}], "Princeton is down")))
mixed = [inc[0], {"kind": "unconfirmed", "reason": "Heard Jackson might close, not confirmed."}]
case("rumor mixed with a real incident is accepted, not sent back",
     not validate(w, dates, mixed, "Princeton plant is down from 2027-03-15 to 2027-03-17. Heard Jackson might close."))
plan, bad, failed = run("T-07", mixed)
esc = [a for a in plan["actions"] if a["tool"] == "escalate"]
case("rumor mixed with a real incident: the real one is handled, the rumor gets exactly one escalation, all checks pass",
     plan["action_counts"].get("mes.reschedule", 0) + plan["action_counts"].get("mes.transfer", 0) > 0
     and len(esc) == 1 and not bad and not failed, f"{bad[:2]} {failed[:2]}")
case("noise and rumor alone still need a single clear answer",
     any("mixed" in e for e in validate(w, dates, [{"kind": "noise"}, {"kind": "unconfirmed", "reason": "x"}], "hello")))

import copy

types = lambda path: [n.split(":")[0] for n in path]
delay = run("T-08", [{"kind": "supplier_delay", "plant": "Huntsville", "part": "surround-view cameras",
                      "original_eta": "Monday Mar 29", "new_eta": "Thursday Apr 1"}])[0]["incidents"][0]
outage = run("T-09", [{"kind": "plant_outage", "plant": "Jackson", "start": "2027-03-26", "end": "2027-03-30"}])[0]["incidents"][0]
quality = run("T-10", [{"kind": "quality_hold", "plant": lot["plant_id"], "part": lot["part_id"], "lot_id": lot["lot_id"]}])[0]["incidents"][0]
case("graph evidence follows the required path for each incident kind",
     types(delay["evidence"]["example"]) == ["Shipment", "Part", "Model", "ProductionOrder", "CustomerOrder", "Dealer", "Customer"]
     and types(outage["evidence"]["example"]) == ["Plant", "ProductionOrder", "CustomerOrder", "Dealer", "Customer"]
     and types(quality["evidence"]["example"])[:4] == ["Lot", "ProductionOrder", "Vehicle", "Dealer"]
     and all(c["ok"] for r in (delay, outage, quality) for c in r["evidence"]["fact_check"]))
forged = copy.deepcopy(delay)
forged["resolution"]["shipment"]["part_id"] = "TIRE-20"
forged["resolution"]["part"]["id"] = "TIRE-20"
case("graph fact check rejects a claim that is not an edge in the graph",
     any(not c["ok"] for c in kg.fact_check(forged)))

linked = lambda path: all(kg.g.has_edge(u, v) or kg.g.has_edge(v, u) for u, v in zip(path, path[1:]))
grouped = {"dealer.notify": "customer_order_ids", "dealer.stop_sale": "vins"}
bad = []
for eid, inc in (("T-11", mixed[:1] + [{"kind": "supplier_delay", "plant": "Princeton", "part": ship["part_id"],
                                         "original_eta": "2027-03-15", "new_eta": "2027-03-19"}]),
                 ("T-12", [{"kind": "quality_hold", "plant": lot["plant_id"], "part": lot["part_id"], "lot_id": lot["lot_id"]}])):
    for a in run(eid, inc)[0]["actions"]:
        paths = a.get("paths") or [a["path"]]
        if a["tool"] in grouped and len(paths) != len(a["args"][grouped[a["tool"]]]):
            bad.append(f"{a['tool']} has {len(paths)} paths for {len(a['args'][grouped[a['tool']]])} records")
        for p in paths:
            if not linked(p[:-1] if a["tool"] in ("mes.reschedule", "mes.transfer") else p):
                bad.append(f"{a['tool']} path is not a chain of graph edges: {p}")
case("every grouped action has one graph path per record, and every path is a chain of real graph edges", not bad, bad[:3])

import views
base ={"classification": "Plant Outage", "checks": [{"ok": True}]}
case("status: resolved only when every action was accepted, partial when some were",
     views.status(dict(base, execution={"sent": 5, "ok": 5, "complete": True})) == "resolved"
     and views.status(dict(base, execution={"sent": 3, "ok": 3, "complete": False})) == "partial"
     and views.status(dict(base, execution=None)) == "verified"
     and views.status(dict(base, execution={"sent": 5, "ok": 0, "complete": False})) == "failed"
     and views.status(dict(base, checks=[{"ok": False}], execution={"sent": 5, "ok": 5, "complete": True})) == "blocked")

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
