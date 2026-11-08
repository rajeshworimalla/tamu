"""The four agents: Coordinator, Supply Chain Planner, Dealer and Customer Care, Quality."""
from collections import defaultdict
from datetime import date

from .graph import nid
from .types import Kind, Placement, Tool
from .types import LOANER_TIERS, REAL_KINDS, TIER_RANK
from .world import LAST_IDX, iso, resolve_incident

LABELS = {Kind.PLANT_OUTAGE: "Plant Outage", Kind.SUPPLIER_DELAY: "Supplier Delay", Kind.QUALITY_HOLD: "Quality Hold"}


def day(text):
    d = date.fromisoformat(text)
    return f"{d:%b} {d.day}"


def act(tool, args, agent, rule, reason, path, targets):
    """One proposed tool call with its agent, rule, reason and graph path."""
    return {"tool": tool, "args": args, "agent": agent, "rule": rule, "reason": reason, "path": path,
            "targets": targets}


class Ledger:
    """Shared build-slot ledger for one event, so compound incidents never double-book."""
    def __init__(self, w):
        self.w = w
        self.loc = {po: (o["plant_id"], o["idx"]) for po, o in w.pos.items() if o["idx"] >= 0}
        self.slots = defaultdict(set)
        for po, at in self.loc.items():
            self.slots[at].add(po)
        self.blocks = []

    def blocked(self, plant, idx, model):
        """True when the plant cannot build this model on that day."""
        return any(p == plant and a <= idx < b and model in ms for p, a, b, ms in self.blocks)

    def free(self, plant, idx):
        """True when the plant has a free slot that day."""
        return len(self.slots[(plant, idx)]) < self.w.plants[plant]["slots"]

    def place(self, po, d) -> Placement:
        """Earliest same-plant slot after the disruption; otherwise transfer (handbook rule 3)."""
        model, plant = self.w.pos[po]["model"], d["plant"]
        start = max(0, d["earliest_same_plant_idx"])
        for i in range(start, LAST_IDX + 1):
            if self.free(plant, i) and not self.blocked(plant, i, model):
                return Placement(Tool.RESCHEDULE, plant, i, f"earliest free {plant} slot on or after {iso(start)}")
        # Transfers prefer days after the disruption; earlier days only if none is left.
        for i in list(range(start, LAST_IDX + 1)) + list(range(0, start)):
            for p in self.w.plant_order:
                if p != plant and model in self.w.plants[p]["models"] and self.free(p, i) and not self.blocked(p, i, model):
                    why = (f"{plant} has no free slot {iso(start)} to {iso(LAST_IDX)}; earliest free slot at another plant "
                           f"building {model}" + ("" if i >= start else ", none left after the disruption"))
                    return Placement(Tool.TRANSFER, p, i, why)
        return Placement(None, None, None, "no feasible slot in the planning window")

    def options(self, po, d, tool, plant, idx):
        """Every option considered for a build and why it was rejected or chosen."""
        model, home = self.w.pos[po]["model"], d["plant"]
        start, cap = max(0, d["earliest_same_plant_idx"]), self.w.plants[home]["slots"]
        city = lambda p: self.w.plants[p]["city"].split(",")[0]
        seq = list(range(start, LAST_IDX + 1)) + list(range(0, start))
        out = [{"option": f"{city(home)} before {day(iso(start))}", "verdict": "not allowed, the disruption is still on (rule 3)"}] \
            if 0 < start <= LAST_IDX else [{"option": city(home), "verdict": "down through the end of the window"}] \
            if start > LAST_IDX else []
        runs = []
        for i in range(start, idx if tool == Tool.RESCHEDULE else LAST_IDX + 1):
            why = "still blocked" if self.blocked(home, i, model) else f"full, {cap} of {cap} slots taken"
            if runs and runs[-1][2] == why and runs[-1][1] == i - 1:
                runs[-1][1] = i
            else:
                runs.append([i, i, why])
        out += [{"option": f"{city(home)} {day(iso(a))}" + (f" to {day(iso(b))}" if b > a else ""), "verdict": why}
                for a, b, why in runs]
        if tool != Tool.RESCHEDULE:
            for p in self.w.plant_order:
                if p == home or p == plant:
                    continue
                if model not in self.w.plants[p]["models"]:
                    out.append({"option": city(p), "verdict": f"does not build the {model.title()}"})
                    continue
                first = next((i for i in seq if self.free(p, i) and not self.blocked(p, i, model)), None)
                out.append({"option": city(p), "verdict": "full or down every day in the window" if first is None else
                            f"also free {day(iso(first))}, {city(plant)} comes first in the plant list" if first == idx else
                            f"first free slot {day(iso(first))}, later than the chosen day"})
        if tool == Tool.RESCHEDULE:
            out.append({"option": "Another plant", "verdict": "not considered, rule 3 allows a transfer only when this plant has no free slot"})
        if tool:
            out.append({"option": f"{city(plant)} {day(iso(idx))}", "verdict": "chosen, earliest feasible slot", "chosen": True})
        return out

    def apply(self, po, plant, idx):
        """Moves a build in the ledger."""
        self.slots[self.loc[po]].discard(po)
        self.loc[po] = (plant, idx)
        self.slots[(plant, idx)].add(po)


class SupplyChainPlanner:
    """Finds affected builds through the graph and moves each one (rules 1 to 3)."""
    name = "Supply Chain Planner"

    def __init__(self, w, kg):
        self.w, self.kg = w, kg

    def impact(self, r):
        """Affected builds and their graph paths for one disruption."""
        d = r["disruption"]
        if r["kind"] == Kind.SUPPLIER_DELAY:
            return self.kg.delay_impact(r["resolution"]["shipment"]["shipment_id"], d["from_idx"], d["to_idx_excl"])
        return self.kg.outage_impact(d["plant"], d["from_idx"], d["to_idx_excl"])

    def plan(self, disruptions, ledger):
        """Moves every affected build once, earliest first, and collects the waiting customer orders."""
        work, seen = [], set()
        for r in disruptions:
            hits = self.impact(r)
            r["affected_production_orders"] = sorted(po for po, _ in hits)
            for po, path in hits:
                if po not in seen:
                    seen.add(po)
                    work.append((self.w.pos[po]["idx"], po, r, path))
        work.sort(key=lambda x: (x[0], x[1]))
        actions, affected = [], {}
        for _, po, r, path in work:
            o = self.w.pos[po]
            tool, plant, idx, why = ledger.place(po, r["disruption"])
            tried = ledger.options(po, r["disruption"], tool, plant, idx)
            if tool is None:
                others = [p for p in self.w.plant_order if o["model"] in self.w.plants[p]["models"]]
                why = (f"No policy-compliant slot for {po} ({o['model'].title()}): every plant that builds it "
                       f"({', '.join(self.w.plants[p]['city'].split(',')[0] for p in others)}) is full or down "
                       f"every day through {iso(LAST_IDX)}. A person must decide.")
                actions.append(act(Tool.ESCALATE, {"reason": why}, self.name, "3", why, path, [nid("ProductionOrder", po)]))
                actions[-1]["alternatives"] = tried
                continue
            ledger.apply(po, plant, idx)
            args = {"production_order_id": po, "new_date": iso(idx)}
            if tool == Tool.TRANSFER:
                args = {"production_order_id": po, "to_plant_id": plant, "new_date": iso(idx)}
            reason = f"{o['model']} order built {o['build_date']} at {o['plant_id']} moves to {plant} {iso(idx)}: {why}"
            r.setdefault("moves", []).append({"production_order_id": po, "tool": tool, "to": f"{plant} {iso(idx)}"})
            actions.append(act(tool, args, self.name, "3", reason, path + [nid("Plant", plant)],
                               [nid("ProductionOrder", po)]))
            actions[-1]["alternatives"] = tried
            for co, dealer, customer in self.kg.orders_downstream(po):
                affected[co] = {"dealer": dealer, "customer": customer, "po": po, "new_date": iso(idx),
                                "path": path + [nid("CustomerOrder", co)]}
        return actions, affected


class CustomerCare:
    """Dealer notices and loaners (rules 4 and 5)."""
    name = "Dealer and Customer Care"

    def __init__(self, w):
        self.w = w

    def plan(self, affected):
        """One notice per dealer; loaners by tier, promised date and order id within each pool."""
        actions, by_dealer, entitled = [], defaultdict(list), defaultdict(list)
        for co, a in affected.items():
            by_dealer[a["dealer"]].append(co)
            tier = self.w.customers[a["customer"]]["tier"]
            if tier in LOANER_TIERS:
                entitled[a["dealer"]].append((TIER_RANK[tier], self.w.cos[co]["promised_date"], co))
        for dealer in sorted(by_dealer):
            ids = sorted(by_dealer[dealer])
            lines = "; ".join(f"{co} now builds {affected[co]['new_date']}" for co in ids)
            actions.append(act(Tool.NOTIFY_DEALER, {"dealer_id": dealer, "customer_order_ids": ids,
                                                 "message": f"Production delay for your customer orders: {lines}."},
                               self.name, "4", f"{len(ids)} of this dealer's customer orders are delayed",
                               affected[ids[0]]["path"] + [nid("Dealer", dealer)],
                               [nid("Dealer", dealer)] + [nid("CustomerOrder", c) for c in ids]))
            actions[-1]["paths"] = [affected[c]["path"] + [nid("Dealer", dealer)] for c in ids]
        granted, denied = [], []
        for dealer in sorted(entitled):
            queue, pool = sorted(entitled[dealer]), self.w.loaners.get(dealer, 0)
            for rank, (tier, promised, co) in enumerate(queue):
                (granted if rank < pool else denied).append((dealer, tier, promised, co, rank + 1, pool, len(queue)))
        for dealer, tier, promised, co, rank, pool, size in sorted(granted):
            name = [k for k, v in TIER_RANK.items() if v == tier][0]
            actions.append(act(Tool.ASSIGN_LOANER, {"customer_order_id": co}, self.name, "5",
                               f"{name} customer, promised {promised}, priority {rank} of {size} for {pool} loaners at {dealer}",
                               affected[co]["path"] + [nid("Customer", affected[co]["customer"])],
                               [nid("CustomerOrder", co), nid("Customer", affected[co]["customer"])]))
        return actions, [{"customer_order_id": co, "dealer_id": d, "priority": f"{rank} of {size}", "pool": pool}
                         for d, _, _, co, rank, pool, size in denied]


class QualityAgent:
    """Lot holds, stop-sales and owner notices (rule 6)."""
    name = "Quality"

    def __init__(self, kg):
        self.kg = kg

    def plan(self, r):
        """Holds the lot, stops its unsold cars per dealer and contacts each owner."""
        actions = []
        part = r["resolution"]["part"]["id"]
        for lot in r["resolution"]["lots"]:
            lot_id, vehicles = lot["lot_id"], sorted(self.kg.lot_impact(lot["lot_id"]), key=lambda v: v["vin"])
            lot_node = nid("Lot", lot_id)
            actions.append(act(Tool.HOLD_LOT, {"lot_id": lot_id}, self.name, "6",
                               f"{part} lot {lot_id} reported defective, built into {len(vehicles)} vehicles",
                               [lot_node], [lot_node]))
            unsold = defaultdict(list)
            for v in vehicles:
                if v["status"] == "in_stock":
                    unsold[v["dealer"]].append(v)
            for dealer in sorted(unsold):
                vins = [v["vin"] for v in unsold[dealer]]
                actions.append(act(Tool.STOP_SALE, {"dealer_id": dealer, "vins": vins}, self.name, "6",
                                   f"{len(vins)} unsold vehicles from lot {lot_id} at this dealer",
                                   unsold[dealer][0]["path"] + [nid("Dealer", dealer)],
                                   [nid("Dealer", dealer)] + [nid("Vehicle", x) for x in vins]))
                actions[-1]["paths"] = [v["path"] + [nid("Dealer", dealer)] for v in unsold[dealer]]
            owners = defaultdict(list)
            for v in vehicles:
                if v["status"] == "sold":
                    owners[v["customer"]].append(v)
            for cust in sorted(owners):
                vins = ", ".join(v["vin"] for v in owners[cust])
                actions.append(act(Tool.NOTIFY_CUSTOMER, {"customer_id": cust, "message":
                                   f"Quality notice: your vehicle {vins} contains {part} from lot {lot_id}, now on "
                                   f"quality hold. Your dealer will contact you to schedule an inspection."},
                                   self.name, "6", f"owner of sold vehicle {vins} from lot {lot_id}",
                                   owners[cust][0]["path"] + [nid("Customer", cust)],
                                   [nid("Customer", cust)] + [nid("Vehicle", v["vin"]) for v in owners[cust]]))
                actions[-1]["paths"] = [v["path"] + [nid("Customer", cust)] for v in owners[cust]]
        return actions


class Coordinator:
    """Classifies the event, routes incidents to the specialists and assembles the plan."""
    name = "Coordinator"

    def __init__(self, w, kg, dates):
        self.w, self.kg, self.dates = w, kg, dates
        self.supply, self.care, self.quality = SupplyChainPlanner(w, kg), CustomerCare(w), QualityAgent(kg)

    def classify(self, incidents):
        """Event class from its incidents."""
        real = [i["kind"] for i in incidents if i["kind"] in REAL_KINDS]
        if not real:
            return "Unconfirmed Report" if any(i["kind"] == Kind.UNCONFIRMED for i in incidents) else "Noise"
        if len(real) > 1:
            return "Compound (" + " + ".join(LABELS[k] for k in real) + ")"
        return LABELS[real[0]]

    def handle(self, event, incidents):
        """Builds the full plan for one event; nothing is executed here."""
        eid = event["event_id"]
        plan = {"event_id": eid, "text": event["text"], "source": event.get("source", ""),
                "received_at": event.get("received_at", ""), "classification": self.classify(incidents),
                "incidents": [resolve_incident(self.w, self.dates, i) for i in incidents], "loaners_denied": []}
        self.kg.add_event(eid, event["text"], plan["classification"])
        real = [r for r in plan["incidents"] if r["kind"] in REAL_KINDS]
        if not real:
            unconfirmed = [i for i in incidents if i["kind"] == Kind.UNCONFIRMED]
            reason = (unconfirmed or incidents)[0].get("reason", "")
            for r in plan["incidents"]:
                r["evidence"] = {"required_path": "reason the report was not actionable" if unconfirmed
                                 else "reason the event was judged not relevant", "reason": reason}
            plan["summary"] = ("Escalated to a human: " if unconfirmed else "No action, not operational: ") + reason
            plan["actions"] = [act(Tool.ESCALATE, {"reason": "Unconfirmed or non-specific report: " + reason}, self.name,
                                   "8", reason, [nid("Event", eid)], [nid("Event", eid)])] if unconfirmed else []
            return self.finish(plan)
        failed = [c["claim"] for r in real for c in self.kg.fact_check(r) if not c["ok"]]
        if failed:
            reason = "Graph fact check failed: " + "; ".join(failed)
            plan["summary"] = "Escalated to a human: " + reason
            plan["actions"] = [act(Tool.ESCALATE, {"reason": reason}, self.name, "8", reason, [nid("Event", eid)], [nid("Event", eid)])]
            return self.finish(plan)
        ledger = Ledger(self.w)
        disruptions = [r for r in real if "disruption" in r]
        for r in disruptions:
            d = r["disruption"]
            ledger.blocks.append((d["plant"], d["from_idx"], d["to_idx_excl"], set(d["models"])))
        moves, affected = self.supply.plan(disruptions, ledger)
        care, plan["loaners_denied"] = self.care.plan(affected) if affected else ([], [])
        quality = [a for r in real if r["kind"] == Kind.QUALITY_HOLD for a in self.quality.plan(r)]
        rumors = [act(Tool.ESCALATE, {"reason": "Unconfirmed or non-specific report: " + i.get("reason", "")}, self.name, "8",
                      i.get("reason", ""), [nid("Event", eid)], [nid("Event", eid)]) for i in incidents if i["kind"] == Kind.UNCONFIRMED]
        plan["actions"] = moves + care + quality + rumors
        for r in real:
            r["evidence"] = self.kg.evidence(r)
        plan["summary"] = " ".join(s[0].upper() + s[1:] + "." for s in map(self.describe, real)) + \
            (" The unconfirmed part was handed to a person." if rumors else "")
        return self.finish(plan)

    def describe(self, r):
        """One plain-English sentence for an incident."""
        res, d = r["resolution"], r.get("disruption", {})
        moved = len(r.get("moves", []))
        if r["kind"] == Kind.PLANT_OUTAGE:
            return (f"{self.w.plants[d['plant']]['city']} plant down {day(iso(d['from_idx']))} to "
                    f"{day(iso(d['to_idx_excl'] - 1))}, {moved} builds moved")
        part = self.w.parts[res["part"]["id"]]["name"]
        if r["kind"] == Kind.SUPPLIER_DELAY:
            return (f"{part} for {self.w.plants[d['plant']]['city']} arrives {day(res['new_eta']['date'])} instead of "
                    f"{day(res['original_eta']['date'])}, {moved} builds moved")
        lots = res["lots"]
        vehicles = sum(len(self.kg.lot_impact(l["lot_id"])) for l in lots)
        return f"{part} lot {', '.join(l['lot_id'] for l in lots)} on hold, {vehicles} vehicles traced"

    def finish(self, plan):
        """Records every action in the graph and counts them."""
        for n, a in enumerate(plan["actions"]):
            self.kg.record(plan["event_id"], n, a)
        counts = defaultdict(int)
        for a in plan["actions"]:
            counts[a["tool"]] += 1
        plan["action_counts"] = dict(counts)
        return plan
