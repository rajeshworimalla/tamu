"""Shapes plans and graph data for the web app. Pure functions and one Presenter; no file or network I/O."""
import json
from collections import Counter, defaultdict
from datetime import date

from run import trace
from tower.types import MOVES, Kind, Status, Tool
from tower.world import LAST_IDX, date_to_idx, iso

FIRST = -10
GROUP_AT = {"ProductionOrder": 24, "Plant": 24, "Model": 24, "Part": 24}
GROUP_NAMES = {"CustomerOrder": "customer orders", "ProductionOrder": "builds", "Customer": "customers",
               "Dealer": "dealers", "Vehicle": "vehicles"}
ID_LABELLED = ("Customer", "CustomerOrder", "ProductionOrder", "Vehicle")
HIDDEN = ("Action", "Rule")


def status(plan) -> Status:
    """Status from the plan's checks and the enterprise server's answers; never optimistic."""
    if plan["classification"] == "Noise":
        return Status.IGNORED
    if plan["classification"] == "Unconfirmed Report":
        return Status.REVIEW
    if not all(c["ok"] for c in plan["checks"]):
        return Status.BLOCKED
    run = plan.get("execution")
    if run and run["complete"]:
        return Status.RESOLVED
    if run and run["sent"]:
        return Status.PARTIAL if run["ok"] else Status.FAILED
    return Status.VERIFIED


def action_key(tool, args):
    """Identity of a call, ignoring free text, used to match plans against a server log."""
    return tool + json.dumps({k: v for k, v in args.items() if k not in ("message", "reason")}, sort_keys=True)


def match_log(plan, rows):
    """Marks each planned action accepted or not from the server's log rows for this event."""
    if rows is None:
        return None
    accepted = {action_key(r["tool"], r["args"]) for r in rows if r["ok"]}
    for a in plan["actions"]:
        a["executed"] = action_key(a["tool"], a["args"]) in accepted
    complete = all(a["executed"] for a in plan["actions"]) and len(rows) == len(plan["actions"])
    return {"sent": len(rows), "ok": sum(r["ok"] for r in rows), "complete": complete}


def record_results(plan, server, event_id, stopped):
    """Execution summary from the server's response to each sent action."""
    for a in plan["actions"]:
        a["executed"] = "result" in a and "error" not in a["result"]
    ok = sum(a["executed"] for a in plan["actions"])
    first_error = next((a["result"]["error"] for a in plan["actions"] if "error" in a.get("result", {})), None)
    return {"sent": sum("result" in a for a in plan["actions"]), "ok": ok, "complete": ok == len(plan["actions"]),
            "server": server, "server_event_id": event_id, "stopped": stopped, "error": first_error}


def tagline(world, plan):
    bits = []
    for r in plan["incidents"]:
        res = r["resolution"]
        if "plant" in res:
            city = world.plants[res["plant"]["id"]]["city"].split(",")[0]
            what = world.parts[res["part"]["id"]]["name"] if "part" in res else "assembly plant"
            bits.append(f"{city} · {what}")
    return "  +  ".join(bits) or plan["text"][:70]


def target(a):
    """Short description of what an action touches, for the audit table."""
    g = a["args"]
    for k in ("production_order_id", "lot_id", "dealer_id", "customer_order_id", "customer_id"):
        if k in g:
            extra = f" ({len(g['customer_order_ids'])} orders)" if "customer_order_ids" in g else \
                f" ({len(g['vins'])} vehicles)" if "vins" in g else ""
            to = f" to {g.get('to_plant_id', '')} {g['new_date']}".replace("  ", " ") if "new_date" in g else ""
            return f"{g[k]}{extra}{to}"
    return g.get("reason", "")[:80]


def schedule(world, plan):
    """Before and after positions of every build near the moved ones, for the recovery timeline."""
    moves = {a["args"]["production_order_id"]: a["args"] for a in plan["actions"] if a["tool"] in MOVES}
    if not moves:
        return None
    hits = [r["disruption"] for r in plan["incidents"] if "disruption" in r]
    after = {po: (m.get("to_plant_id", world.pos[po]["plant_id"]), date_to_idx(date.fromisoformat(m["new_date"])))
             for po, m in moves.items()}
    plants = {d["plant"] for d in hits} | {p for p, _ in after.values()}
    plants = [p for p in world.plant_order if p in plants]
    span = [world.pos[po]["idx"] for po in moves] + [i for _, i in after.values()]
    lo, hi = max(0, min(span) - 1), min(LAST_IDX, max(span) + 1)
    orders = []
    for po, o in world.pos.items():
        if o["idx"] < 0 or not (po in moves or (o["plant_id"] in plants and lo <= o["idx"] <= hi)):
            continue
        orders.append({"po": po, "model": o["model"], "before": [o["plant_id"], o["idx"]],
                       "after": list(after.get(po, (o["plant_id"], o["idx"]))), "moved": po in moves,
                       "transfer": po in moves and after[po][0] != o["plant_id"]})
    shift = [after[po][1] - world.pos[po]["idx"] for po in moves]
    return {"plants": [{"id": p, "city": world.plants[p]["city"].split(",")[0], "slots": world.plants[p]["slots"]} for p in plants],
            "days": [{"idx": i, "date": iso(i)} for i in range(lo, hi + 1)], "orders": orders,
            "blocked": [{"plant": d["plant"], "from": max(lo, d["from_idx"]), "to": min(hi, d["to_idx_excl"] - 1),
                         "models": d["models"], "part": d.get("part")} for d in hits],
            "moved": len(moves), "transferred": sum(o["transfer"] for o in orders),
            "avg_shift": round(sum(shift) / len(shift), 1)}


def hub(world, plan, owned):
    """Counts for the Operations impact hub: causes on one side, reach on the other."""
    real = [r for r in plan["incidents"] if "plant" in r["resolution"]]
    if not real:
        return None
    plants, suppliers, parts, builds, dealers, customers = [], set(), set(), set(), set(), set()
    for r in real:
        res = r["resolution"]
        if res["plant"]["id"] not in plants:
            plants.append(res["plant"]["id"])
        if "shipment" in res:
            suppliers.add(res["shipment"]["supplier_id"])
            parts.add(res["shipment"]["part_id"])
        for lot in res.get("lots", []):
            suppliers.add(lot["supplier_id"])
            parts.add(lot["part_id"])
        builds |= set(r.get("affected_production_orders", []))
    for a in plan["actions"]:
        g, tool = a["args"], a["tool"]
        if tool in MOVES:
            builds.add(g["production_order_id"])
        elif tool == Tool.NOTIFY_DEALER:
            dealers.add(g["dealer_id"])
            customers |= {world.cos[c]["customer_id"] for c in g["customer_order_ids"]}
        elif tool == Tool.STOP_SALE:
            dealers.add(g["dealer_id"])
            builds |= {world.vehicles[v]["production_order_id"] for v in g["vins"]}
        elif tool == Tool.NOTIFY_CUSTOMER:
            customers.add(g["customer_id"])
            builds |= {world.vehicles[v]["production_order_id"] for v in owned.get(g["customer_id"], [])}
    models = sorted({world.pos[b]["model"] for b in builds if b in world.pos})

    def names(ids, table):
        return [table[i]["name"] for i in sorted(ids)]

    return {"center": [{"id": p, "city": world.plants[p]["city"].split(",")[0]} for p in plants],
            "counts": {"supplier": len(suppliers), "parts": len(parts), "models": len(models), "builds": len(builds),
                       "dealers": len(dealers), "customers": len(customers)},
            "names": {"supplier": names(suppliers, world.suppliers), "parts": names(parts, world.parts),
                      "models": [m.title() for m in models]}}


def calendar(world, plans):
    """Disruption blocks per plant and day, for the Analytics calendar."""
    blocks = []
    for p in plans.values():
        for r in p["incidents"]:
            if "disruption" in r:
                d = r["disruption"]
                outage = r["kind"] == Kind.PLANT_OUTAGE
                blocks.append({"event": p["event_id"], "plant": d["plant"], "from": max(FIRST, d["from_idx"]),
                               "to": min(LAST_IDX, d["to_idx_excl"] - 1), "kind": "outage" if outage else "delay",
                               "label": "plant down" if outage else f"no {world.parts[d['part']]['name']}"})
            for lot in r["resolution"].get("lots", []):
                blocks.append({"event": p["event_id"], "plant": lot["plant_id"], "kind": "quality",
                               "from": date_to_idx(date.fromisoformat(lot["first_build_date"])),
                               "to": date_to_idx(date.fromisoformat(lot["last_build_date"])),
                               "label": f"{world.parts[lot['part_id']]['name']} lot {lot['lot_id']}"})
    return {"days": [{"idx": i, "date": iso(i)} for i in range(FIRST, LAST_IDX + 1)],
            "plants": [{"id": k, "city": world.plants[k]["city"].split(",")[0]} for k in world.plant_order], "blocks": blocks}


def totals(plans):
    t = {"builds_moved": 0, "transferred": 0, "orders_delayed": 0, "dealer_notices": 0, "loaners": 0, "vehicles_stopped": 0,
         "owners_contacted": 0, "lots_held": 0}
    for p in plans.values():
        for a in p["actions"]:
            g, tool = a["args"], a["tool"]
            t["builds_moved"] += tool in MOVES
            t["transferred"] += tool == Tool.TRANSFER
            t["orders_delayed"] += len(g.get("customer_order_ids", [])) if tool == Tool.NOTIFY_DEALER else 0
            t["dealer_notices"] += tool == Tool.NOTIFY_DEALER
            t["loaners"] += tool == Tool.ASSIGN_LOANER
            t["vehicles_stopped"] += len(g.get("vins", [])) if tool == Tool.STOP_SALE else 0
            t["owners_contacted"] += tool == Tool.NOTIFY_CUSTOMER
            t["lots_held"] += tool == Tool.HOLD_LOT
    return t


def audit(plans):
    """Every action with its rule, rehearsal result and server result, plus the rule matrix."""
    rows = []
    for p in plans.values():
        failed = " | ".join(p.get("rehearsal_failed", []))
        for n, a in enumerate(p["actions"]):
            rows.append({"event": p["event_id"], "n": n, "tool": a["tool"], "agent": a["agent"], "rule": a["rule"],
                         "target": target(a), "reason": a["reason"],
                         "ok": not failed or f"{a['tool']} {a['args']}" not in failed, "sent": a.get("executed")})
    return {"rows": rows, "matrix": {p["event_id"]: {c["rule"]: c["ok"] for c in p["checks"]} for p in plans.values()}}


class Presenter:
    """Builds every API response from the world, the graph and the plans."""

    def __init__(self, world, kg):
        self.world, self.kg = world, kg
        self.owned = defaultdict(list)
        self.owner_dealer = {}
        for vin, v in world.vehicles.items():
            if v["customer_id"]:
                self.owned[v["customer_id"]].append(vin)
                self.owner_dealer[v["customer_id"]] = v["dealer_id"]

    def label(self, n):
        d = self.kg.g.nodes[n]
        extra = f" {d['tier']}" if d.get("tier") else ""
        return f"{n.split(':', 1)[1]}{extra}" if d["type"] in ID_LABELLED else d.get("label", n)

    def relation(self, u, v):
        for a, b in ((u, v), (v, u)):
            data = self.kg.g.get_edge_data(a, b)
            if data:
                return next(iter(data.values()))["rel"]
        return ""

    def ripple(self, plan):
        """The plan's graph paths as one layered graph, grouping large layers."""
        layer, edges, tools = {}, set(), defaultdict(Counter)
        for a in plan["actions"]:
            p = a["path"]
            for i, n in enumerate(p):
                layer[n] = min(layer.get(n, i), i)
            edges |= set(zip(p, p[1:]))
            for t in a["targets"]:
                if t in layer or t == p[-1]:
                    tools[t][a["tool"]] += 1
        by_type = defaultdict(list)
        for n in layer:
            by_type[self.kg.g.nodes[n]["type"]].append(n)
        group = {n: f"Group:{t}" for t, ns in by_type.items() if len(ns) > GROUP_AT.get(t, 8) for n in ns}
        nodes = {}
        for n, lv in layer.items():
            t = self.kg.g.nodes[n]["type"]
            if n in group:
                g = nodes.setdefault(group[n], {"id": group[n], "type": t, "layer": lv, "count": 0, "tools": Counter(),
                                                "members": []})
                g["count"] += 1
                g["layer"] = min(g["layer"], lv)
                g["tools"].update(tools[n])
                g["members"].append(n)
            else:
                nodes[n] = {"id": n, "type": t, "label": self.label(n), "layer": lv, "tools": dict(tools[n])}
        for g in nodes.values():
            if "count" in g:
                g["label"] = f"{g['count']} {GROUP_NAMES.get(g['type'], g['type'].lower() + 's')}"
                g["tools"] = dict(g["tools"])
                g["members"] = [{"id": m, "label": self.label(m)} for m in sorted(g["members"])[:40]]
        links = {}
        for u, v in sorted(edges):
            a, b = group.get(u, u), group.get(v, v)
            if a != b:
                links[(a, b)] = {"source": a, "target": b, "rel": self.relation(u, v)}
        return {"nodes": list(nodes.values()), "edges": list(links.values())}

    def geo(self, plan):
        """Plants, suppliers, transfers and per-dealer counts for the impact map."""
        w = self.world
        plants, suppliers, transfers, dealers = set(), set(), [], defaultdict(Counter)
        for r in plan["incidents"]:
            res = r["resolution"]
            if "plant" in res:
                plants.add(res["plant"]["id"])
            if "shipment" in res:
                suppliers.add(res["shipment"]["supplier_id"])
            for lot in res.get("lots", []):
                suppliers.add(lot["supplier_id"])
                plants.add(lot["plant_id"])
        for a in plan["actions"]:
            t, g = a["tool"], a["args"]
            if t == Tool.TRANSFER:
                transfers.append({"from": w.pos[g["production_order_id"]]["plant_id"], "to": g["to_plant_id"]})
            elif t == Tool.NOTIFY_DEALER:
                dealers[g["dealer_id"]]["orders"] += len(g["customer_order_ids"])
            elif t == Tool.ASSIGN_LOANER:
                dealers[w.cos[g["customer_order_id"]]["dealer_id"]]["loaners"] += 1
            elif t == Tool.STOP_SALE:
                dealers[g["dealer_id"]]["stopped"] += len(g["vins"])
            elif t == Tool.NOTIFY_CUSTOMER and g["customer_id"] in self.owner_dealer:
                dealers[self.owner_dealer[g["customer_id"]]]["owners"] += 1
        return {"plants": sorted(plants), "suppliers": sorted(suppliers), "transfers": transfers,
                "dealers": {d: dict(c) for d, c in sorted(dealers.items())}}

    def summary(self, plan):
        checks = plan["checks"]
        return {"event_id": plan["event_id"], "text": plan["text"], "classification": plan["classification"],
                "source": plan["source"], "received_at": plan["received_at"], "summary": plan["summary"],
                "actions": len(plan["actions"]), "passed": sum(c["ok"] for c in checks), "checks": len(checks),
                "read_by": plan["read_by"]["handled_by"], "model": plan["read_by"]["model"],
                "status": status(plan), "tagline": tagline(self.world, plan),
                "failed_calls": len(plan.get("rehearsal_failed", [])), "execution": plan.get("execution")}

    def before(self, a):
        po = a["args"].get("production_order_id")
        if po in self.world.pos and "new_date" in a["args"]:
            return {"plant": self.world.pos[po]["plant_id"], "date": self.world.pos[po]["build_date"]}
        return None

    def detail(self, plan):
        """Everything the Incidents page shows for one event."""
        actions = [dict({k: a[k] for k in ("agent", "tool", "args", "rule", "reason", "path")},
                        executed=a.get("executed"), before=self.before(a), alternatives=a.get("alternatives"))
                   for a in plan["actions"]]
        return dict(self.summary(plan), summary=plan["summary"], incidents=plan["incidents"], checks=plan["checks"],
                    actions=actions, counts=plan["action_counts"], loaners_denied=plan["loaners_denied"], ms=plan["ms"],
                    attempts=plan["read_by"].get("attempts") or [], ripple=self.ripple(plan), geo=self.geo(plan),
                    schedule=schedule(self.world, plan), hub=hub(self.world, plan, self.owned))

    def overview(self, plans):
        real = [p for p in plans.values() if p["actions"] and p["classification"] != "Unconfirmed Report"]
        customers = {a["args"].get("customer_id") or self.world.cos.get(a["args"].get("customer_order_id", ""), {}).get("customer_id")
                     for p in real for a in p["actions"] if a["tool"] in (Tool.ASSIGN_LOANER, Tool.NOTIFY_CUSTOMER)}
        delayed = {co for p in real for a in p["actions"] if a["tool"] == Tool.NOTIFY_DEALER for co in a["args"]["customer_order_ids"]}
        g = self.kg.g
        return {"events": [self.summary(p) for p in plans.values()],
                "totals": {"events": len(plans), "actions": sum(len(p["actions"]) for p in plans.values()),
                           "checks_passed": sum(c["ok"] for p in plans.values() for c in p["checks"]),
                           "checks": sum(len(p["checks"]) for p in plans.values()),
                           "orders_delayed": len(delayed), "customers_reached": len(customers - {None}),
                           "local": sum(p["read_by"]["handled_by"] == "ollama" for p in plans.values()),
                           "tools": Counter(a["tool"] for p in plans.values() for a in p["actions"]),
                           "graph_nodes": g.number_of_nodes(), "graph_edges": g.number_of_edges()},
                "ontology": self.kg.ontology()}

    def board(self, plans):
        """Network footprint across all events, for Analytics."""
        footprint = {"plants": {}, "suppliers": set(), "dealers": defaultdict(Counter), "transfers": []}
        for p in plans.values():
            g = self.geo(p)
            for k in g["plants"]:
                footprint["plants"][k] = footprint["plants"].get(k, 0) + 1
            footprint["suppliers"] |= set(g["suppliers"])
            footprint["transfers"] += g["transfers"]
            for d, c in g["dealers"].items():
                footprint["dealers"][d].update(c)
        footprint.update(suppliers=sorted(footprint["suppliers"]),
                         dealers={d: dict(c) for d, c in footprint["dealers"].items()})
        return {"events": [self.summary(p) for p in plans.values()], "calendar": calendar(self.world, plans),
                "totals": totals(plans), "geo": footprint}

    def audit(self, plans):
        return dict(audit(plans), events=[self.summary(p) for p in plans.values()])

    def find(self, name):
        """A graph node by full id or by its key alone (C1633, PO-0442); None if unknown."""
        name = name.strip()
        if name in self.kg.g:
            return name
        hits = [n for n in self.kg.g if n.split(":", 1)[-1].lower() == name.lower() and self.kg.g.nodes[n]["type"] != "Action"]
        return hits[0] if hits else None

    def why(self, node):
        return {"node": node, "type": self.kg.g.nodes[node]["type"], "label": self.label(node), "stories": self.kg.why(node)}

    def search(self, q, limit=24):
        q = q.strip().lower()
        if len(q) < 2:
            return []
        out = []
        for n, d in self.kg.g.nodes(data=True):
            if d["type"] in HIDDEN:
                continue
            if q in n.lower() or q in str(d.get("label", "")).lower():
                out.append({"id": n, "type": d["type"], "label": self.label(n), "exact": n.lower().endswith(":" + q)})
                if len(out) > 400:
                    break
        return sorted(out, key=lambda x: (not x["exact"], len(x["label"])))[:limit]

    def node(self, nid, cap=14):
        """One record with its neighbours grouped by relation, and the actions taken on it."""
        g = self.kg.g
        d = g.nodes[nid]
        groups = {}
        for direction, edges in (("out", g.out_edges(nid, data=True)), ("in", g.in_edges(nid, data=True))):
            for u, v, e in edges:
                other = v if direction == "out" else u
                t = g.nodes[other]["type"]
                if t in ("Action", "Rule", "Event"):
                    continue
                groups.setdefault(f"{e['rel']}|{direction}|{t}", []).append(other)
        neighbors, more = [], []
        for key, ids in groups.items():
            rel, direction, t = key.split("|")
            for o in sorted(ids)[:cap]:
                neighbors.append({"id": o, "type": t, "label": self.label(o), "rel": rel, "dir": direction})
            if len(ids) > cap:
                more.append({"rel": rel, "dir": direction, "type": t, "hidden": len(ids) - cap})
        info = {k: v for k, v in d.items() if k not in ("type", "label") and not isinstance(v, (list, dict))}
        return {"id": nid, "type": d["type"], "label": self.label(nid), "info": info, "neighbors": neighbors, "more": more,
                "stories": self.kg.why(nid)}

    def report(self, plan):
        """Markdown incident report: the trace, how the model read it, and the execution result."""
        lines = ["", "## How the AI read it", ""]
        for n, a in enumerate(plan["read_by"].get("attempts") or [], 1):
            outcome = "passed every check" if not a.get("errors") else "rejected: " + "; ".join(a["errors"])
            retry = " (retry with feedback)" if a.get("retry") else ""
            lines.append(f"- Attempt {n}{retry}: {a.get('model') or a.get('provider')}, {a.get('ms')} ms, {outcome}")
        if len(lines) == 3:
            lines.append("- Read from the reference extraction")
        run = plan.get("execution")
        lines += ["", "## Execution", "",
                  f"- {run['ok']} of {run['sent']} calls accepted by the company systems" if run and run["sent"]
                  else "- Not sent to the company systems"]
        return trace(plan, plan["checks"], plan["read_by"]) + "\n".join(lines) + "\n"
