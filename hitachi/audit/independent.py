import csv
import json
import os
import sys
from collections import defaultdict, Counter
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "_package", "hack_the_highway_package")
DATA = os.path.join(PKG, "data")
LOG = os.path.join(ROOT, "submission", "action_log.jsonl")
OUT = os.path.dirname(os.path.abspath(__file__))

TODAY = date(2027, 3, 8)
LAST = 19
WRITE = {"mes.reschedule", "mes.transfer", "dealer.notify", "dealer.stop_sale", "crm.assign_loaner",
         "crm.notify_customer", "quality.hold_lot"}
READ = {"mes.get_schedule", "crm.loaner_availability"}

EVENTS = {
    "E-01": {"kind": "compound", "incidents": [
        {"kind": "outage", "plant": "P_TX", "start": "2027-03-19", "end": "2027-03-22",
         "quote": "San Antonio update ... dark from next Friday through Monday Mar 22",
         "note": "next Friday read as Fri 2027-03-19 (Friday of next week); same convention as item 2 where it must be after next Monday"},
        {"kind": "delay", "plant": "P_IN", "part": "CHIP-IVI", "supplier": "SUP-12", "shipment": "SH-0190",
         "orig_eta": "2027-03-15", "new_eta": "2027-03-19",
         "quote": "Quanta: the infotainment chip run for Princeton can't make it next Monday. Carrier says next Friday now",
         "note": "next Monday = 2027-03-15 matches SH-0190 ETA; next Friday = 2027-03-19"}]},
    "E-02": {"kind": "unconfirmed", "quote": "Rumor ... something may be off with a seat material ... nothing confirmed"},
    "E-03": {"kind": "quality", "plant": "P_MS", "part": "CHIP-IVI", "supplier": "SUP-06", "lot": "LOT-0130",
             "first": "2027-02-25", "last": "2027-03-01",
             "quote": "Kestrel ... infotainment chip sent to Jackson ... built Thursday Feb 25 through last Monday",
             "note": "last Monday = 2027-03-01"},
    "E-04": {"kind": "outage", "plant": "P_KY", "start": "2027-03-16", "end": "2027-03-18",
             "quote": "The Kentucky plant ... dark from next Tuesday through next Thursday",
             "note": "ambiguous: next Tuesday could be 2027-03-09 (tomorrow); chose week-of-Mar-15 reading for consistency with E-01"},
    "E-05": {"kind": "noise", "quote": "Dealer Amarillo, TX asks where to find the new brochure PDF."},
    "E-06": {"kind": "noise", "quote": "Dealer Little Rock, AR asks where to find the new brochure PDF."},
    "E-07": {"kind": "noise", "quote": "Dealer Pensacola, FL asks where to find the new brochure PDF."},
    "E-08": {"kind": "outage", "plant": "P_KY", "start": "2027-03-24", "end": "2027-03-25",
             "quote": "Lexington (P_KY) ... stopped from 2027-03-24 through 2027-03-25 inclusive"},
    "E-09": {"kind": "delay", "plant": "P_AL", "part": "CAM-360", "supplier": "SUP-11", "shipment": "SH-0256",
             "orig_eta": "2027-03-29", "new_eta": "2027-04-01",
             "quote": "Orbit: the surround-view cameras run for Huntsville can't make it Monday Mar 29. Carrier says Thursday Apr 1"},
    "E-10": {"kind": "delay", "plant": "P_AL", "part": "BATT-60", "supplier": "SUP-18", "shipment": "SH-0248",
             "orig_eta": "2027-03-29", "new_eta": "2027-04-01",
             "quote": "Huntsville line is waiting on 60 kWh battery packs from Lumen. Original drop was Monday Mar 29, new ETA is Thursday Apr 1"},
    "E-11": {"kind": "outage", "plant": "P_MS", "start": "2027-03-26", "end": "2027-03-30",
             "quote": "Jackson update ... dark from Friday Mar 26 through Tuesday Mar 30"},
    "E-12": {"kind": "delay", "plant": "P_IN", "part": "CAM-360", "supplier": "SUP-11", "shipment": "SH-0182",
             "orig_eta": "2027-03-15", "new_eta": "2027-03-18",
             "quote": "Shipment SH-0182 of CAM-360 ... Princeton (P_IN) was due 2027-03-15 and will now arrive 2027-03-18"},
    "E-13": {"kind": "unconfirmed", "quote": "possible shortage of something electronic sometime soon. Not confirmed by anyone."},
    "E-14": {"kind": "quality", "plant": "P_TX", "part": "HARN-B", "supplier": "SUP-07", "lot": "LOT-0017",
             "first": "2027-02-22", "last": "2027-02-24",
             "quote": "Atlas ... heavy-duty wiring harness sent to the Texas plant ... built Monday Feb 22 through Wednesday Feb 24"},
    "E-15": {"kind": "quality", "plant": "P_IN", "part": "CHIP-IVI", "supplier": "SUP-12", "lot": "LOT-0191",
             "first": "2027-03-02", "last": "2027-03-03",
             "quote": "Lot LOT-0191 (CHIP-IVI, supplier SUP-12) installed at P_IN on vehicles built 2027-03-02 to 2027-03-03"},
}


def d2i(s):
    d = date.fromisoformat(s) if isinstance(s, str) else s
    n = (d - TODAY).days
    if n % 7 > 4:
        raise ValueError("weekend")
    return 5 * (n // 7) + n % 7


def i2d(i):
    return (TODAY + timedelta(days=7 * (i // 5) + i % 5)).isoformat()


def rd(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


plants = {r["plant_id"]: int(r["slots_per_day"]) for r in rd("plants.csv")}
plant_order = [r["plant_id"] for r in rd("plants.csv")]
plant_models = defaultdict(set)
for r in rd("plant_models.csv"):
    plant_models[r["plant_id"]].add(r["model"])
bom = defaultdict(set)
for r in rd("bom.csv"):
    bom[r["model"]].add(r["part_id"])
pos = {r["production_order_id"]: {"plant": r["plant_id"], "idx": d2i(r["build_date"]), "model": r["model"]}
       for r in rd("production_orders.csv")}
cos = {r["customer_order_id"]: r for r in rd("customer_orders.csv")}
cos_by_po = defaultdict(list)
for c in cos.values():
    cos_by_po[c["production_order_id"]].append(c)
tier = {r["customer_id"]: r["tier"] for r in rd("customers.csv")}
pool0 = {r["dealer_id"]: int(r["loaners_available"]) for r in rd("loaners.csv")}
vehicles = rd("finished_vehicles.csv")
lots = {r["lot_id"]: r for r in rd("part_lots.csv")}
ships = {r["shipment_id"]: r for r in rd("inbound_shipments.csv")}


def fresh_slots():
    s = defaultdict(set)
    loc = {}
    for po, o in pos.items():
        if o["idx"] >= 0:
            s[(o["plant"], o["idx"])].add(po)
            loc[po] = (o["plant"], o["idx"])
    return s, loc


def check_interp():
    errs = []
    for eid, ev in EVENTS.items():
        for inc in ev.get("incidents", [ev]):
            if inc["kind"] == "delay":
                sh = ships[inc["shipment"]]
                if (sh["supplier_id"], sh["part_id"], sh["plant_id"], sh["eta_date"]) != (
                        inc["supplier"], inc["part"], inc["plant"], inc["orig_eta"]):
                    errs.append((eid, "shipment mismatch", sh))
            if inc["kind"] == "quality":
                lt = lots[inc["lot"]]
                if (lt["part_id"], lt["supplier_id"], lt["plant_id"], lt["first_build_date"], lt["last_build_date"]) != (
                        inc["part"], inc["supplier"], inc["plant"], inc["first"], inc["last"]):
                    errs.append((eid, "lot mismatch", lt))
                cands = [k for k, v in lots.items() if v["part_id"] == inc["part"] and v["supplier_id"] == inc["supplier"]
                         and v["plant_id"] == inc["plant"] and v["first_build_date"] <= inc["last"]
                         and v["last_build_date"] >= inc["first"]]
                if cands != [inc["lot"]]:
                    errs.append((eid, "lot candidates", cands))
    return errs


def affected(inc):
    if inc["kind"] == "outage":
        a, b = d2i(inc["start"]), d2i(inc["end"])
        res = [p for p, o in pos.items() if o["plant"] == inc["plant"] and a <= o["idx"] <= b and o["idx"] >= 0]
        return res, b + 1
    a, b = d2i(inc["orig_eta"]), d2i(inc["new_eta"])
    res = [p for p, o in pos.items() if o["plant"] == inc["plant"] and inc["part"] in bom[o["model"]]
           and a <= o["idx"] < b and o["idx"] >= 0]
    return res, b


def plan_moves(incs, order="date", transfer_from="end", plant_rank="csv"):
    slots, loc = fresh_slots()
    items = []
    for n, inc in enumerate(incs):
        aff, end = affected(inc)
        for p in aff:
            items.append((n, p, end))
    if order == "date":
        items.sort(key=lambda t: (pos[t[1]]["idx"], t[1]))
    elif order == "po":
        items.sort(key=lambda t: t[1])
    elif order == "incident":
        items.sort(key=lambda t: (t[0], pos[t[1]]["idx"], t[1]))
    rank = plant_order if plant_rank == "csv" else sorted(plant_order)
    moves = {}
    for n, p, end in items:
        pl, cur = loc[p]
        tgt = None
        for i in range(max(end, 0), LAST + 1):
            if len(slots[(pl, i)]) < plants[pl]:
                tgt = ("mes.reschedule", pl, i)
                break
        if tgt is None:
            start = max(end, 0) if transfer_from == "end" else 0
            for i in range(start, LAST + 1):
                for q in rank:
                    if q != pl and pos[p]["model"] in plant_models[q] and len(slots[(q, i)]) < plants[q]:
                        tgt = ("mes.transfer", q, i)
                        break
                if tgt:
                    break
        if tgt is None:
            moves[p] = ("unplaceable", None, None)
            continue
        slots[(pl, cur)].discard(p)
        slots[(tgt[1], tgt[2])].add(p)
        loc[p] = (tgt[1], tgt[2])
        moves[p] = tgt
    return moves, items


def loaner_plan(aff_cos, groups=None):
    pool = dict(pool0)
    given = []
    seqs = groups if groups else [aff_cos]
    for g in seqs:
        ent = [c for c in g if tier[c["customer_id"]] in ("Platinum", "Gold")]
        ent.sort(key=lambda c: (0 if tier[c["customer_id"]] == "Platinum" else 1, c["promised_date"], c["customer_order_id"]))
        for c in ent:
            if c["customer_order_id"] in given:
                continue
            if pool[c["dealer_id"]] > 0:
                pool[c["dealer_id"]] -= 1
                given.append(c["customer_order_id"])
    return given


def expected_for(eid, ev, **kw):
    kind = ev["kind"]
    out = {"moves": {}, "notify": {}, "loaners": [], "stop_sale": {}, "customers": [], "holds": [], "escalate": 0,
           "affected_pos": [], "end_by_po": {}, "inc_of_po": {}}
    if kind == "noise":
        return out
    if kind == "unconfirmed":
        out["escalate"] = 1
        return out
    if kind == "quality":
        lt = lots[ev["lot"]]
        a, b = lt["first_build_date"], lt["last_build_date"]
        vs = [v for v in vehicles if v["plant_id"] == lt["plant_id"] and a <= v["build_date"] <= b
              and lt["part_id"] in bom[v["model"]]]
        out["holds"] = [ev["lot"]]
        ss = defaultdict(list)
        cs = set()
        for v in vs:
            if v["status"] == "in_stock":
                ss[v["dealer_id"]].append(v["vin"])
            elif v["status"] == "sold":
                cs.add(v["customer_id"])
        out["stop_sale"] = {k: sorted(v) for k, v in sorted(ss.items())}
        out["customers"] = sorted(cs)
        out["vehicles"] = len(vs)
        return out
    incs = ev.get("incidents", [ev])
    moves, items = plan_moves(incs, **kw)
    out["moves"] = {p: [t, pl, i2d(i) if i is not None else None] for p, (t, pl, i) in sorted(moves.items())}
    out["affected_pos"] = sorted(moves)
    for n, p, end in items:
        out["end_by_po"][p] = end
        out["inc_of_po"][p] = n
    aff_cos = [c for p in sorted(moves) for c in cos_by_po[p]]
    nd = defaultdict(list)
    for c in aff_cos:
        nd[c["dealer_id"]].append(c["customer_order_id"])
    out["notify"] = {k: sorted(v) for k, v in sorted(nd.items())}
    out["loaners"] = sorted(loaner_plan(aff_cos))
    if len(incs) > 1:
        groups = [[c for p in sorted(moves) if out["inc_of_po"][p] == n for c in cos_by_po[p]] for n in range(len(incs))]
        out["loaners_sequential_alt"] = sorted(loaner_plan(aff_cos, groups))
    out["affected_cos"] = len(aff_cos)
    return out


def load_log():
    with open(LOG, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def date_ok(s):
    try:
        i = d2i(s)
    except Exception:
        return False
    return 0 <= i <= LAST


def compare(eid, ev, exp, calls):
    r = {"failed_calls": [], "read_calls": 0, "duplicates": [], "invalid_dates": [], "missing": [], "extra": [],
         "wrong_args": [], "capacity_violations": [], "loaner_overallocation": [], "non_earliest_moves": [],
         "unaffected_moves": [], "counts_expected": Counter(), "counts_actual": Counter()}
    ok = []
    for c in calls:
        if not c.get("ok"):
            r["failed_calls"].append(c)
            continue
        if c["tool"] in READ:
            r["read_calls"] += 1
            continue
        ok.append(c)
        r["counts_actual"][c["tool"]] += 1
    ce = r["counts_expected"]
    for p, m in exp["moves"].items():
        ce[m[0]] += 1
    ce["dealer.notify"] = len(exp["notify"])
    ce["crm.assign_loaner"] = len(exp["loaners"])
    ce["dealer.stop_sale"] = len(exp["stop_sale"])
    ce["crm.notify_customer"] = len(exp["customers"])
    ce["quality.hold_lot"] = len(exp["holds"])
    ce["escalate"] = exp["escalate"]
    r["counts_expected"] = {k: v for k, v in ce.items() if v}
    r["counts_actual"] = dict(r["counts_actual"])

    by = defaultdict(list)
    for c in ok:
        by[c["tool"]].append(c["args"])
    seen = Counter()
    act_moves = {}
    for t in ("mes.reschedule", "mes.transfer"):
        for a in by[t]:
            p = a["production_order_id"]
            seen[p] += 1
            if not date_ok(a.get("new_date")):
                r["invalid_dates"].append({"tool": t, "args": a})
            act_moves[p] = [t, a.get("to_plant_id", pos[p]["plant"] if p in pos else None), a.get("new_date")]
    r["duplicates"] += [{"tool": "move", "production_order_id": p, "times": n} for p, n in seen.items() if n > 1]
    for p, m in exp["moves"].items():
        if p not in act_moves:
            r["missing"].append({"tool": m[0], "production_order_id": p, "expected": m})
        elif act_moves[p] != m:
            r["wrong_args"].append({"production_order_id": p, "expected": m, "actual": act_moves[p]})
    for p, m in act_moves.items():
        if p not in exp["moves"]:
            r["extra"].append({"tool": m[0], "production_order_id": p, "actual": m})
            r["unaffected_moves"].append(p)

    an = defaultdict(set)
    nn = Counter()
    for a in by["dealer.notify"]:
        an[a["dealer_id"]] |= set(a["customer_order_ids"])
        nn[a["dealer_id"]] += 1
    r["duplicates"] += [{"tool": "dealer.notify", "dealer_id": d, "times": n} for d, n in nn.items() if n > 1]
    for d, ids in exp["notify"].items():
        if d not in an:
            r["missing"].append({"tool": "dealer.notify", "dealer_id": d, "customer_order_ids": ids})
        elif an[d] != set(ids):
            r["wrong_args"].append({"tool": "dealer.notify", "dealer_id": d, "missing_ids": sorted(set(ids) - an[d]),
                                    "extra_ids": sorted(an[d] - set(ids))})
    for d in an:
        if d not in exp["notify"]:
            r["extra"].append({"tool": "dealer.notify", "dealer_id": d, "customer_order_ids": sorted(an[d])})

    lc = Counter(a["customer_order_id"] for a in by["crm.assign_loaner"])
    r["duplicates"] += [{"tool": "crm.assign_loaner", "customer_order_id": k, "times": n} for k, n in lc.items() if n > 1]
    el = set(exp["loaners"])
    for k in sorted(el - set(lc)):
        c = cos[k]
        r["missing"].append({"tool": "crm.assign_loaner", "customer_order_id": k, "dealer": c["dealer_id"],
                             "tier": tier[c["customer_id"]], "promised": c["promised_date"]})
    for k in sorted(set(lc) - el):
        c = cos.get(k, {})
        r["extra"].append({"tool": "crm.assign_loaner", "customer_order_id": k, "dealer": c.get("dealer_id"),
                           "tier": tier.get(c.get("customer_id")), "promised": c.get("promised_date")})
    used = Counter(cos[k]["dealer_id"] for k in lc if k in cos)
    for d, n in used.items():
        if n > pool0[d]:
            r["loaner_overallocation"].append({"dealer_id": d, "assigned": n, "pool": pool0[d]})

    sc = defaultdict(set)
    snn = Counter()
    for a in by["dealer.stop_sale"]:
        sc[a["dealer_id"]] |= set(a["vins"])
        snn[a["dealer_id"]] += 1
    r["duplicates"] += [{"tool": "dealer.stop_sale", "dealer_id": d, "times": n} for d, n in snn.items() if n > 1]
    for d, v in exp["stop_sale"].items():
        if d not in sc:
            r["missing"].append({"tool": "dealer.stop_sale", "dealer_id": d, "vins": v})
        elif sc[d] != set(v):
            r["wrong_args"].append({"tool": "dealer.stop_sale", "dealer_id": d, "missing_vins": sorted(set(v) - sc[d]),
                                    "extra_vins": sorted(sc[d] - set(v))})
    for d in sc:
        if d not in exp["stop_sale"]:
            r["extra"].append({"tool": "dealer.stop_sale", "dealer_id": d, "vins": sorted(sc[d])})

    cc = Counter(a["customer_id"] for a in by["crm.notify_customer"])
    r["duplicates"] += [{"tool": "crm.notify_customer", "customer_id": k, "times": n} for k, n in cc.items() if n > 1]
    for k in sorted(set(exp["customers"]) - set(cc)):
        r["missing"].append({"tool": "crm.notify_customer", "customer_id": k})
    for k in sorted(set(cc) - set(exp["customers"])):
        r["extra"].append({"tool": "crm.notify_customer", "customer_id": k})

    hc = Counter(a["lot_id"] for a in by["quality.hold_lot"])
    r["duplicates"] += [{"tool": "quality.hold_lot", "lot_id": k, "times": n} for k, n in hc.items() if n > 1]
    for k in sorted(set(exp["holds"]) - set(hc)):
        r["missing"].append({"tool": "quality.hold_lot", "lot_id": k})
    for k in sorted(set(hc) - set(exp["holds"])):
        r["extra"].append({"tool": "quality.hold_lot", "lot_id": k})

    ne = len(by["escalate"])
    if ne < exp["escalate"]:
        r["missing"].append({"tool": "escalate"})
    if ne > exp["escalate"]:
        r["extra"].append({"tool": "escalate", "times": ne})
    if ne > 1:
        r["duplicates"].append({"tool": "escalate", "times": ne})

    slots, loc = fresh_slots()
    for c in ok:
        if c["tool"] not in ("mes.reschedule", "mes.transfer"):
            continue
        a = c["args"]
        p = a["production_order_id"]
        if p not in loc or not date_ok(a.get("new_date")):
            continue
        pl, cur = loc[p]
        tp = a.get("to_plant_id", pl)
        ti = d2i(a["new_date"])
        end = exp["end_by_po"].get(p)
        if end is not None:
            if c["tool"] == "mes.reschedule":
                if ti < end:
                    r["non_earliest_moves"].append({"po": p, "issue": "before disruption end", "date": a["new_date"]})
                for i in range(end, ti):
                    if len(slots[(pl, i)]) < plants[pl]:
                        r["non_earliest_moves"].append({"po": p, "issue": "earlier same-plant slot free at that point",
                                                        "free_day": i2d(i), "chosen": a["new_date"]})
                        break
            else:
                if pos[p]["model"] not in plant_models[tp]:
                    r["non_earliest_moves"].append({"po": p, "issue": "target plant does not build model"})
                fr = [i2d(i) for i in range(end, LAST + 1) if len(slots[(pl, i)]) < plants[pl]]
                if fr:
                    r["non_earliest_moves"].append({"po": p, "issue": "transfer while same-plant slot free", "free": fr})
                for i in range(end, ti):
                    alt = [q for q in plant_order if q != pl and pos[p]["model"] in plant_models[q]
                           and len(slots[(q, i)]) < plants[q]]
                    if alt:
                        r["non_earliest_moves"].append({"po": p, "issue": "earlier transfer slot free",
                                                        "day": i2d(i), "plants": alt})
                        break
        slots[(pl, cur)].discard(p)
        slots[(tp, ti)].add(p)
        loc[p] = (tp, ti)
    for (pl, i), s in slots.items():
        if len(s) > plants[pl]:
            r["capacity_violations"].append({"plant": pl, "date": i2d(i), "orders": sorted(s)})
    for p in exp["affected_pos"]:
        end = exp["end_by_po"][p]
        if loc[p][0] == pos[p]["plant"] and loc[p][1] < end:
            r["capacity_violations"].append({"po": p, "issue": "affected order still inside disruption", "at": i2d(loc[p][1])})
    kinds = {c["tool"] for c in ok if c["tool"] in WRITE}
    if ev["kind"] in ("noise", "unconfirmed") and kinds:
        r["extra"].append({"issue": "write tools on noise/unconfirmed", "tools": sorted(kinds)})
    if ev["kind"] not in ("noise", "unconfirmed") and len(kinds) < 3:
        r["extra"].append({"issue": "fewer than three action kinds", "tools": sorted(kinds)})
    return r


def replay(log):
    sys.path.insert(0, PKG)
    import enterprise
    res = {"available": True, "errors": [], "state_checks": {}}
    ent = enterprise.Enterprise(DATA)
    for n, c in enumerate(log):
        try:
            ent.call(c["event_id"], c["tool"], c["args"])
            if not c["ok"]:
                res["errors"].append({"line": n + 1, "issue": "log says failed but replay succeeded"})
        except enterprise.ToolError as e:
            if c["ok"]:
                res["errors"].append({"line": n + 1, "issue": "log says ok but replay failed", "error": str(e), "call": c})
    for eid, s in ent._state.items():
        over = {k: v for k, v in Counter((pl, i) for po, (pl, i) in s["loc"].items()).items() if v > ent.plants[k[0]]["slots"]}
        neg = {d: v for d, v in s["loaners"].items() if v < 0}
        moved = sorted(po for po, (pl, i) in s["loc"].items() if (pl, i) != (ent.orders[po]["plant_id"], ent.orders[po]["idx"]))
        res["state_checks"][eid] = {"capacity_over": [f"{k[0]} {i2d(k[1])}: {v}" for k, v in over.items()],
                                   "negative_pools": neg, "moved": len(moved), "loaned": len(s["loaned"]),
                                   "held": sorted(s["held"]), "stopped": len(s["stopped"]),
                                   "customers": len(s["customers"]), "escalated": s["escalated"],
                                   "notified_dealers": len(s["notified"])}
    return res


def main():
    interp_errs = check_interp()
    log = load_log()
    calls = defaultdict(list)
    for c in log:
        calls[c["event_id"]].append(c)
    expected, comparison, variants = {}, {}, {}
    for eid, ev in EVENTS.items():
        exp = expected_for(eid, ev)
        expected[eid] = {"interpretation": ev, **{k: v for k, v in exp.items() if k not in ("end_by_po", "inc_of_po")}}
        comparison[eid] = compare(eid, ev, exp, calls.get(eid, []))
        if ev["kind"] in ("outage", "delay", "compound"):
            v = {}
            for kw in ({"order": "po"}, {"order": "incident"}, {"transfer_from": "today"}, {"plant_rank": "alpha"}):
                alt = expected_for(eid, ev, **kw)["moves"]
                diff = {p: [exp["moves"][p], alt[p]] for p in alt if alt[p] != exp["moves"][p]}
                v["_".join(f"{a}={b}" for a, b in kw.items())] = diff
            variants[eid] = v
    for eid in calls:
        if eid not in EVENTS:
            comparison[eid] = {"issue": "event not in feed", "calls": len(calls[eid])}
    rep = replay(log)
    with open(os.path.join(OUT, "expected.json"), "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=1)
    summary = {}
    for eid, r in comparison.items():
        if "counts_expected" in r:
            summary[eid] = {"expected": r["counts_expected"], "actual": r["counts_actual"],
                            "issues": {k: len(r[k]) for k in ("failed_calls", "duplicates", "invalid_dates", "missing",
                                                               "extra", "wrong_args", "capacity_violations",
                                                               "loaner_overallocation", "non_earliest_moves")
                                       if r[k]}}
    with open(os.path.join(OUT, "comparison.json"), "w", encoding="utf-8") as f:
        json.dump({"interpretation_check_errors": interp_errs, "log_lines": len(log), "summary": summary,
                   "per_event": comparison, "variant_sensitivity": variants, "replay": rep}, f, indent=1, default=str)
    print(json.dumps({"interp_errs": interp_errs, "summary": summary, "replay_errors": rep["errors"],
                      "variants": variants}, indent=1, default=str))


if __name__ == "__main__":
    main()
