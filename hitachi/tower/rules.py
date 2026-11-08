"""The ten handbook rules, recomputed from the raw tables, plus a rehearsal on a copy of the enterprise."""
import sys
from collections import defaultdict
from datetime import date

from .types import LOANER_TIERS, REAL_KINDS, TIER_RANK, Kind, Tool
from .world import DATA, LAST_IDX, PKG, date_to_idx

WRITES = {Tool.RESCHEDULE, Tool.TRANSFER, Tool.NOTIFY_DEALER, Tool.STOP_SALE, Tool.ASSIGN_LOANER,
          Tool.NOTIFY_CUSTOMER, Tool.HOLD_LOT}


def load_enterprise():
    """The organizer's Enterprise class, used for rehearsal."""
    sys.dont_write_bytecode = True
    if PKG not in sys.path:
        sys.path.insert(0, PKG)
    from enterprise import Enterprise, ToolError
    return Enterprise(DATA), ToolError


class RuleBook:
    """Checks a plan before anything is sent. Independent of the graph and the planner."""
    def __init__(self, w):
        self.w = w
        self.ent, self.tool_error = load_enterprise()
        self.runs = 0

    def rehearse(self, plan):
        """Runs every call on a private copy of the enterprise; returns the failures."""
        self.runs += 1
        sid, failed = f"{plan['event_id']}#rehearsal{self.runs}", []
        for a in plan["actions"]:
            try:
                self.ent.call(sid, a["tool"], a["args"])
            except self.tool_error as e:
                failed.append(f"{a['tool']} {a['args']}: {e}")
        return failed

    def check(self, plan):
        """One result per applicable handbook rule."""
        self.last_failed = []
        w, acts, out = self.w, plan["actions"], []
        by = defaultdict(list)
        for a in acts:
            by[a["tool"]].append(a["args"])
        writes = [a for a in acts if a["tool"] in WRITES]
        real = [r for r in plan["incidents"] if r["kind"] in REAL_KINDS]
        kinds = {r["kind"] for r in plan["incidents"]}

        def rule(n, title, ok, detail=""):
            out.append({"rule": n, "title": title, "ok": bool(ok), "detail": "" if ok else detail})

        if not real:
            if Kind.UNCONFIRMED in kinds:
                rule(8, "Unconfirmed report: escalate, no operational change",
                     not writes and len(by[Tool.ESCALATE]) == 1, f"{len(writes)} writes, {len(by['escalate'])} escalations")
            else:
                rule(7, "Noise: no action at all", not acts, f"{len(acts)} actions")
            return out

        moved = {a["production_order_id"]: a for t in (Tool.RESCHEDULE, Tool.TRANSFER) for a in by[t]}
        expected, earliest, due = {}, {}, set()
        for r in real:
            if "disruption" not in r:
                continue
            d = r["disruption"]
            hit = {po for po, o in w.pos.items() if o["plant_id"] == d["plant"] and o["model"] in d["models"]
                   and max(0, d["from_idx"]) <= o["idx"] < d["to_idx_excl"]}
            n = 1 if r["kind"] == Kind.SUPPLIER_DELAY else 2
            title = "Delay: every build needing the part in the gap is moved" if n == 1 else \
                "Outage: every build at the plant in the outage is moved"
            rule(n, title, hit <= set(moved), f"not moved: {sorted(hit - set(moved))}")
            for po in hit:
                expected[po] = d
                earliest[po] = max(earliest.get(po, 0), d["earliest_same_plant_idx"])

        slots = defaultdict(set)
        for po, o in w.pos.items():
            if o["idx"] >= 0:
                slots[(o["plant_id"], o["idx"])].add(po)
        for po, a in moved.items():
            o = w.pos[po]
            slots[(o["plant_id"], o["idx"])].discard(po)
            slots[(a.get("to_plant_id", o["plant_id"]), date_to_idx(date.fromisoformat(a["new_date"])))].add(po)
        bad = []
        for po, a in moved.items():
            o, idx = w.pos[po], date_to_idx(date.fromisoformat(a["new_date"]))
            if "to_plant_id" not in a and idx < earliest.get(po, 0):
                bad.append(f"{po} rescheduled before the disruption ends")
            if "to_plant_id" in a:
                if o["model"] not in w.plants[a["to_plant_id"]]["models"]:
                    bad.append(f"{po} sent to a plant that does not build {o['model']}")
                cap = w.plants[o["plant_id"]]["slots"]
                if any(len(slots[(o["plant_id"], i)]) < cap for i in range(earliest.get(po, 0), LAST_IDX + 1)):
                    bad.append(f"{po} transferred although {o['plant_id']} still has a free slot")
        if moved or expected:
            rule(3, "Rescheduling: after the disruption, transfer only when the plant is full", not bad, "; ".join(bad))

        if expected:
            want = defaultdict(set)
            for po in expected:
                for co in w.cos_by_po[po]:
                    want[w.cos[co]["dealer_id"]].add(co)
            got = defaultdict(list)
            for a in by[Tool.NOTIFY_DEALER]:
                got[a["dealer_id"]].append(set(a["customer_order_ids"]))
            ok = set(got) == set(want) and all(len(v) == 1 and v[0] == want[k] for k, v in got.items())
            rule(4, "Dealers: one notice each, listing exactly their affected orders", ok,
                 f"expected {len(want)} dealers, got {len(got)}")

            entitled = defaultdict(list)
            for cos in want.values():
                for co in cos:
                    c = w.cos[co]
                    tier = w.customers[c["customer_id"]]["tier"]
                    if tier in LOANER_TIERS:
                        entitled[c["dealer_id"]].append((TIER_RANK[tier], c["promised_date"], co))
            due = {co for d, q in entitled.items() for *_, co in sorted(q)[:w.loaners.get(d, 0)]}
            given = {a["customer_order_id"] for a in by[Tool.ASSIGN_LOANER]}
            rule(5, "Loaners: Platinum, then Gold, then promised date, within each pool", given == due,
                 f"missing {sorted(due - given)[:5]}, extra {sorted(given - due)[:5]}")

        for r in real:
            if r["kind"] != Kind.QUALITY_HOLD:
                continue
            lots = r["resolution"]["lots"]
            users = set(w.models_using(r["resolution"]["part"]["id"]))
            veh = [v for v in w.vehicles.values() for l in lots if v["plant_id"] == l["plant_id"] and v["model"] in users
                   and l["first_build_date"] <= v["build_date"] <= l["last_build_date"]]
            stop = defaultdict(set)
            for v in veh:
                if v["status"] == "in_stock":
                    stop[v["dealer_id"]].add(v["vin"])
            got_stop = defaultdict(set)
            for a in by[Tool.STOP_SALE]:
                got_stop[a["dealer_id"]] |= set(a["vins"])
            owners = {v["customer_id"] for v in veh if v["status"] == "sold"}
            told = {a["customer_id"] for a in by[Tool.NOTIFY_CUSTOMER]}
            ok = ({a["lot_id"] for a in by[Tool.HOLD_LOT]} == {l["lot_id"] for l in lots}
                  and dict(got_stop) == dict(stop) and told == owners)
            rule(6, "Quality: hold the lot, stop unsold vehicles, contact every owner", ok,
                 f"{len(veh)} vehicles, {len(owners)} owners expected, {len(told)} contacted")

        kinds = {a["tool"] for a in writes}
        no_loaner_owed = bool(expected) and not due and Tool.NOTIFY_DEALER in kinds
        rule(9, "Completeness: at least three kinds of action, unless no loaner is owed", len(kinds) >= 3 or no_loaner_owed,
             f"kinds: {sorted(kinds)}")
        extra = sorted(set(moved) - set(expected)) if expected else sorted(moved)
        failed = self.last_failed = self.rehearse(plan)
        rule(10, "Nothing unaffected is touched, every call succeeds in rehearsal",
             not extra and not failed and not [e for e in by[Tool.ESCALATE] if not e["reason"].startswith("Unconfirmed")],
             f"extra moves {extra[:5]}, failed {failed[:3]}")
        return out
