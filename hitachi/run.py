"""Batch run: read, plan, check and execute the 15 events, then write traces and exports."""
import argparse
import json
import os
import urllib.error
import urllib.request

from tower.agents import Coordinator
from tower.graph import KnowledgeGraph, nid
from tower.rules import RuleBook
from tower.types import Tool
from tower.world import DATA, DateResolver, World

HERE = os.path.dirname(os.path.abspath(__file__))


def load_incidents(args, world, dates, events):
    """The model's reading of every event, or hand-written readings with --reference (development only)."""
    if args.reference:
        print(f"DEVELOPMENT MODE: events are not read by the model; using the hand-written readings in {args.reference}\n")
        src = json.load(open(args.reference, encoding="utf-8"))["events"]
        return {k: {"incidents": v, "handled_by": "reference", "model": None} for k, v in src.items()}
    import extract
    extract.require_model()
    chain = extract.providers()
    return {e["event_id"]: extract.extract_event(world, dates, e, chain) for e in events}


def guard(plan, checks):
    """Replaces a plan that failed any rule with one escalation that lists the failures."""
    failed = [c for c in checks if not c["ok"]]
    if not failed or not plan["actions"]:
        return plan
    reason = "Plan failed policy checks: " + "; ".join(f"rule {c['rule']} {c['detail']}" for c in failed)
    plan["blocked_actions"] = plan["actions"]
    plan["actions"] = [{"tool": Tool.ESCALATE, "args": {"reason": reason}, "agent": "Coordinator", "rule": "8",
                        "reason": reason, "path": [nid("Event", plan["event_id"])],
                        "targets": [nid("Event", plan["event_id"])]}]
    return plan


def execute(url, plan):
    """Sends each call once; stops at the first unanswered call and never retries a write."""
    failed = 0
    for n, a in enumerate(plan["actions"]):
        body = json.dumps({"event_id": plan["event_id"], "tool": a["tool"], "args": a["args"]}).encode()
        req = urllib.request.Request(url.rstrip("/") + "/act", body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                a["result"] = json.loads(r.read())
        except urllib.error.HTTPError as e:
            a["result"] = json.loads(e.read() or b"{}") or {"error": str(e)}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            a["result"] = {"error": f"server stopped answering ({getattr(e, 'reason', e)}); this call may or may not have been applied"}
            for b in plan["actions"][n + 1:]:
                b["result"] = {"error": "not sent, run stopped"}
            plan["stopped"] = (f"Stopped at {plan['event_id']} call {n + 1} of {len(plan['actions'])}: the server stopped answering. "
                               f"{n} calls of this event were sent first. Check action_log.jsonl for call {n + 1}. "
                               f"Do not rerun on the same server: restart it with --overwrite and a fresh --out.")
            return failed + 1
        failed += "error" in a["result"]
    return failed


def short(args):
    """Arguments without free text, for trace tables."""
    return ", ".join(f"{k}={v if not isinstance(v, list) else f'{len(v)} ids'}"
                     for k, v in args.items() if k not in ("message", "reason"))


def trace(plan, checks, source):
    """Readable Markdown trace of one event."""
    lines = [f"# {plan['event_id']}: {plan['classification']}", "", f"> {plan['text']}", "",
             f"**Decision:** {plan['summary']}", "",
             f"**Read by:** {source.get('handled_by')} {source.get('model') or ''}".rstrip(), "", "## Understanding"]
    for r in plan["incidents"]:
        lines.append(f"- **{r['kind']}**")
        for field, v in r["resolution"].items():
            if isinstance(v, dict) and "mention" in v:
                lines.append(f"  - {field}: \"{v['mention']}\" -> {v.get('id') or v.get('date')} ({v.get('via') or v.get('rule')})")
        if "shipment" in r["resolution"]:
            lines.append(f"  - shipment: {r['resolution']['shipment']['shipment_id']}")
        if "lots" in r["resolution"]:
            lines.append(f"  - lots: {', '.join(l['lot_id'] for l in r['resolution']['lots'])}")
        lines += [f"  - warning: {x}" for x in r["warnings"]]
    lines += ["", "## Graph evidence"]
    for r in plan["incidents"]:
        e = r.get("evidence") or {}
        lines += ["", f"**{r['kind']}**: {e.get('required_path', '')}", ""]
        if "reason" in e:
            lines.append(f"- {e['reason']}")
            continue
        lines.append("- Example path: " + " > ".join(e.get("example", [])))
        lines.append("- Records reached: " + ", ".join(f"{k} {v}" for k, v in e.get("counts", {}).items()))
        lines += [f"- Fact check: {c['claim']}: {'confirmed' if c['ok'] else 'NOT in the graph'} ({' '.join(c['edge'])})"
                  for c in e.get("fact_check", [])]
    lines += ["", "## Policy checks", "", "| Rule | Check | Result |", "|---|---|---|"]
    lines += [f"| {c['rule']} | {c['title']} | {'pass' if c['ok'] else 'FAIL ' + c['detail']} |" for c in checks]
    lines += ["", "## Actions", "", "| # | Agent | Tool | Arguments | Rule | Why |", "|---|---|---|---|---|---|"]
    lines += [f"| {n} | {a['agent']} | {a['tool']} | {short(a['args'])} | {a['rule']} | {a['reason']} |"
              for n, a in enumerate(plan["actions"])]
    tried = [a for a in plan["actions"] if a.get("alternatives")]
    if tried:
        lines += ["", "## Options considered for each build", ""]
        lines += [f"- {a['targets'][0].split(':', 1)[-1]}: " + "; ".join(f"{x['option']} {x['verdict']}" for x in a["alternatives"])
                  for a in tried]
    seen, paths = set(), []
    for a in plan["actions"]:
        if a["tool"] not in seen:
            seen.add(a["tool"])
            paths.append(f"- {a['tool']}: " + " -> ".join(a["path"]))
    if paths:
        lines += ["", "## Graph paths", ""] + paths
    if plan["loaners_denied"]:
        lines += ["", "## Loaners not available", ""]
        lines += [f"- {d['customer_order_id']} at {d['dealer_id']}: priority {d['priority']}, pool {d['pool']}"
                  for d in plan["loaners_denied"]]
    results = [a["result"] for a in plan["actions"] if "result" in a]
    if results:
        accepted = sum("error" not in r for r in results)
        lines += ["", "## Execution", "", f"{accepted} of {len(plan['actions'])} calls accepted by the enterprise server."]
        lines += [f"- call {n}: {a['result']['error']}" for n, a in enumerate(plan["actions"]) if "error" in a.get("result", {})]
    return "\n".join(lines) + "\n"


def affected(plan):
    """Records an event reached, by type."""
    pos = sorted({po for r in plan["incidents"] for po in r.get("affected_production_orders", [])})
    cos = sorted({c for a in plan["actions"] if a["tool"] == Tool.NOTIFY_DEALER for c in a["args"]["customer_order_ids"]})
    vins = sorted({v for a in plan["actions"] if a["tool"] == Tool.STOP_SALE for v in a["args"]["vins"]})
    owners = sorted({a["args"]["customer_id"] for a in plan["actions"] if a["tool"] == Tool.NOTIFY_CUSTOMER})
    lots = sorted({a["args"]["lot_id"] for a in plan["actions"] if a["tool"] == Tool.HOLD_LOT})
    return {"production_orders": pos, "customer_orders": cos, "lots": lots, "unsold_vehicles": vins, "owners": owners}


def record(plan, checks, source):
    """Machine-readable trace of one event."""
    results = [a["result"] for a in plan["actions"] if "result" in a]
    return {
        "event_id": plan["event_id"], "source": plan["source"], "received_at": plan["received_at"], "text": plan["text"],
        "classification": plan["classification"], "decision": plan["summary"],
        "interpretation": {"handled_by": source.get("handled_by"), "model": source.get("model"),
                           "attempts": source.get("attempts") or []},
        "incidents": [{"kind": r["kind"], "extracted": r["raw"], "resolution": r["resolution"],
                       "disruption": r.get("disruption"), "affected_production_orders": r.get("affected_production_orders", []),
                       "warnings": r["warnings"], "graph_evidence": r.get("evidence")} for r in plan["incidents"]],
        "affected_records": affected(plan),
        "policy_checks": checks,
        "actions": [{"n": n, "agent": a["agent"], "tool": a["tool"], "args": a["args"], "rule": a["rule"], "reason": a["reason"],
                     "graph_path": a["path"], "graph_paths": a.get("paths") or [a["path"]], "options_considered": a.get("alternatives"), "result": a.get("result")}
                    for n, a in enumerate(plan["actions"])],
        "loaners_not_available": plan["loaners_denied"],
        "execution": {"sent": len(results), "accepted": sum("error" not in r for r in results),
                      "failed": sum("error" in r for r in results)} if results else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", metavar="FILE", help="development only: skip the model and use hand-written readings, "
                                                        "for example tests/fixtures/reference_readings.json")
    ap.add_argument("--extract", action="store_true", help="kept for compatibility; the model always reads the events")
    ap.add_argument("--execute", metavar="URL")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "run"))
    args = ap.parse_args()
    world, dates = World(), DateResolver()
    kg, events = KnowledgeGraph(world), json.load(open(os.path.join(DATA, "events.json"), encoding="utf-8"))
    tower, rules = Coordinator(world, kg, dates), RuleBook(world)
    sources = load_incidents(args, world, dates, events)
    os.makedirs(os.path.join(args.out, "traces"), exist_ok=True)
    report = []
    for e in events:
        src = sources[e["event_id"]]
        plan = tower.handle(e, src["incidents"])
        checks = rules.check(plan)
        plan = guard(plan, checks)
        failed = execute(args.execute, plan) if args.execute else None
        plan.update(checks=checks, read_by={k: src.get(k) for k in ("handled_by", "model", "attempts")})
        report.append(plan)
        with open(os.path.join(args.out, "traces", f"{e['event_id']}.md"), "w", encoding="utf-8") as f:
            f.write(trace(plan, checks, src))
        with open(os.path.join(args.out, "traces", f"{e['event_id']}.json"), "w", encoding="utf-8") as f:
            json.dump(record(plan, checks, src), f, indent=1, default=str)
        passed = sum(c["ok"] for c in checks)
        print(f"{e['event_id']}  {plan['classification']:<42} {len(plan['actions']):>4} actions  "
              f"rules {passed}/{len(checks)}" + (f"  server failures {failed}" if failed is not None else ""))
        if plan.get("stopped"):
            print("\n" + plan["stopped"])
            break
    json.dump(report, open(os.path.join(args.out, "plan.json"), "w", encoding="utf-8"), indent=1, default=str)
    json.dump(kg.ontology(), open(os.path.join(args.out, "ontology.json"), "w", encoding="utf-8"), indent=1)
    open(os.path.join(args.out, "ontology.mmd"), "w", encoding="utf-8").write(kg.mermaid())
    kg.export(os.path.join(args.out, "graph.json"))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
