"""Company data from the organizer CSVs, plus name and date resolution."""
import csv
import os
import re
from collections import defaultdict
from datetime import date, timedelta

from .types import REAL_KINDS, Kind

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.normpath(os.path.join(HERE, "..", "_package", "hack_the_highway_package"))
DATA = os.path.join(PKG, "data")

TODAY = date(2027, 3, 8)
LAST_IDX = 19
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def idx_to_date(i):
    """Working-day index (0 = today) to a date."""
    return TODAY + timedelta(days=7 * (i // 5) + i % 5)


def date_to_idx(d):
    """Date to working-day index; weekends are an error."""
    days = (d - TODAY).days
    if days % 7 > 4:
        raise ValueError(f"{d} is a weekend")
    return 5 * (days // 7) + days % 7


def iso(i):
    """Working-day index to YYYY-MM-DD."""
    return idx_to_date(i).isoformat()


def first_workday_on_or_after(d):
    while d.weekday() > 4:
        d += timedelta(days=1)
    return date_to_idx(d)


def last_workday_on_or_before(d):
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return date_to_idx(d)


class DateResolver:
    """Turns written dates ('next Friday', 'Mar 22', '3/22') into real dates."""
    def __init__(self, today=TODAY, next_convention="next_week"):
        self.today, self.conv = today, next_convention

    def resolve(self, text):
        """Resolves one written date; contradictions such as a wrong weekday are an error."""
        t = re.sub(r"\s+", " ", re.sub(r"(\d)(?:st|nd|rd|th)\b|,", r"\1 ", text.lower())).strip().rstrip(".").strip()
        t = re.sub(r"^(on|by|the) ", "", t)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
            return date.fromisoformat(t), "iso"
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
        if m:
            y = int(m.group(3) or self.today.year)
            return date(y + 2000 if y < 100 else y, int(m.group(1)), int(m.group(2))), "absolute"
        if t in WEEKDAYS:
            return self.today + timedelta(days=(WEEKDAYS.index(t) - self.today.weekday()) % 7 or 7), "first upcoming"
        if t == "today":
            return self.today, "today"
        if t == "tomorrow":
            return self.today + timedelta(days=1), "tomorrow"
        m = re.fullmatch(r"(next|last|this)\s+(\w+)", t)
        if m and m.group(2) in WEEKDAYS:
            rel, wd = m.group(1), WEEKDAYS.index(m.group(2))
            monday = self.today - timedelta(days=self.today.weekday())
            if rel == "this":
                return monday + timedelta(days=wd), "this week"
            if rel == "last":
                return monday - timedelta(days=7) + timedelta(days=wd), "previous calendar week"
            if self.conv == "next_week":
                return monday + timedelta(days=7 + wd), "next calendar week"
            delta = (wd - self.today.weekday()) % 7 or 7
            return self.today + timedelta(days=delta), "first upcoming"
        m = re.fullmatch(r"(?:(\w+)\s+)?([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?", t)
        if m and m.group(2) in MONTHS:
            d = date(int(m.group(4) or self.today.year), MONTHS[m.group(2)], int(m.group(3)))
            if m.group(1) in WEEKDAYS and WEEKDAYS.index(m.group(1)) != d.weekday():
                raise ValueError(f"weekday and date disagree in {text!r}")
            return d, "absolute"
        raise ValueError(f"cannot parse date {text!r}")


def read_csv(data_dir, name):
    """Rows of one organizer CSV, read by column name."""
    with open(os.path.join(data_dir, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class World:
    """All company tables, indexed by id. Read-only after loading."""
    def __init__(self, data_dir=DATA):
        rd = lambda n: read_csv(data_dir, n)
        self.plants = {r["plant_id"]: dict(r, slots=int(r["slots_per_day"]), models=set()) for r in rd("plants.csv")}
        self.plant_order = list(self.plants)
        for r in rd("plant_models.csv"):
            self.plants[r["plant_id"]]["models"].add(r["model"])
        self.parts = {r["part_id"]: r for r in rd("parts.csv")}
        self.suppliers = {r["supplier_id"]: r for r in rd("suppliers.csv")}
        self.models = {r["model"]: r for r in rd("models.csv")}
        self.bom = defaultdict(set)
        for r in rd("bom.csv"):
            self.bom[r["model"]].add(r["part_id"])
        self.shipments = {r["shipment_id"]: r for r in rd("inbound_shipments.csv")}
        self.lots = {r["lot_id"]: r for r in rd("part_lots.csv")}
        self.pos = {r["production_order_id"]: dict(r, idx=date_to_idx(date.fromisoformat(r["build_date"])),
                                                   units=int(r["units"])) for r in rd("production_orders.csv")}
        self.dealers = {r["dealer_id"]: r for r in rd("dealers.csv")}
        self.customers = {r["customer_id"]: r for r in rd("customers.csv")}
        self.cos = {r["customer_order_id"]: r for r in rd("customer_orders.csv")}
        self.cos_by_po = defaultdict(list)
        for co in self.cos.values():
            self.cos_by_po[co["production_order_id"]].append(co["customer_order_id"])
        self.vehicles = {r["vin"]: r for r in rd("finished_vehicles.csv")}
        self.loaners = {r["dealer_id"]: int(r["loaners_available"]) for r in rd("loaners.csv")}
        self.aliases = defaultdict(list)
        for r in rd("aliases.csv"):
            self.aliases[r["alias"].strip().lower()].append((r["entity_type"], r["entity_id"]))

    def resolve(self, etype, mention):
        """Mention to record id by id, alias, name or containment; unknown or ambiguous is an error."""
        m = mention.strip()
        table = {"plant": self.plants, "part": self.parts, "supplier": self.suppliers}[etype]
        if m in table:
            return m, "id"
        hits = {eid for t, eid in self.aliases.get(m.lower(), []) if t == etype}
        if len(hits) == 1:
            return hits.pop(), "alias"
        if hits:
            raise ValueError(f"ambiguous {etype} {m!r}: {sorted(hits)}")
        exact = [k for k, v in table.items() if v["name"].lower() == m.lower()]
        if len(exact) == 1:
            return exact[0], "name"
        sub = [k for k, v in table.items() if m.lower() in v["name"].lower()]
        if len(sub) == 1:
            return sub[0], "name substring"
        low = f" {re.sub(r'[^a-z0-9_-]+', ' ', m.lower())} "
        inside = {eid for alias, hits in self.aliases.items() for t, eid in hits
                  if t == etype and f" {alias} " in low} | {k for k in table if f" {k.lower()} " in low} | \
                 {k for k, v in table.items() if f" {re.sub(r'[^a-z0-9_-]+', ' ', v['name'].lower()).strip()} " in low}
        if not inside and len(m) > 3:
            inside = {eid for alias, hits in self.aliases.items() for t, eid in hits
                      if t == etype and f" {m.lower()} " in f" {alias} "}
        if len(inside) == 1:
            return inside.pop(), "contained"
        raise ValueError(f"cannot resolve {etype} {m!r} (candidates {sorted(sub or inside)})")

    def models_using(self, part):
        """Models whose bill of materials includes the part."""
        return sorted(m for m, ps in self.bom.items() if part in ps)


def resolve_incident(w, dr, inc):
    """Resolves one reading to real records and dates, or raises when it does not fit the data."""
    k = inc["kind"]
    out = {"kind": k, "raw": inc, "resolution": {}, "warnings": []}
    res = out["resolution"]
    if k not in REAL_KINDS:
        return out
    for et in ("plant", "part", "supplier"):
        if inc.get(et):
            try:
                eid, how = w.resolve(et, inc[et])
            except ValueError as e:
                if et != "supplier":
                    raise
                out["warnings"].append(f"supplier ignored: {e}")
                continue
            res[et] = {"mention": inc[et], "id": eid, "via": how}

    def dt(field):
        d, how = dr.resolve(inc[field])
        res[field] = {"mention": inc[field], "date": d.isoformat(), "rule": how}
        return d

    if k == Kind.PLANT_OUTAGE:
        s, e = dt("start"), dt("end")
        if e < s:
            raise ValueError("outage ends before it starts")
        p = res["plant"]["id"]
        si, ei = first_workday_on_or_after(s), last_workday_on_or_before(e)
        out["disruption"] = {"plant": p, "models": sorted(w.plants[p]["models"]), "from_idx": si,
                             "to_idx_excl": ei + 1, "earliest_same_plant_idx": ei + 1,
                             "summary": f"{p} down {iso(si)} to {iso(ei)}, restarts {iso(ei + 1)}"}
    elif k == Kind.SUPPLIER_DELAY:
        p, part = res["plant"]["id"], res["part"]["id"]
        o, n = dt("original_eta"), dt("new_eta")
        cands = [s for s in w.shipments.values() if s["plant_id"] == p and s["part_id"] == part
                 and s["eta_date"] == o.isoformat()]
        if inc.get("shipment_id"):
            stated = [s for s in cands if s["shipment_id"] == inc["shipment_id"]]
            if not stated:
                out["warnings"].append("stated shipment id does not match part, plant and ETA")
            cands = stated or cands
        if len(cands) != 1:
            raise ValueError(f"shipment not uniquely resolved: {[c['shipment_id'] for c in cands]}")
        sh = res["shipment"] = cands[0]
        if "supplier" in res and res["supplier"]["id"] != sh["supplier_id"]:
            out["warnings"].append(f"supplier in text {res['supplier']['id']} differs from shipment {sh['supplier_id']}")
        if n <= o:
            raise ValueError("new ETA is not after the original ETA")
        oi, ni = first_workday_on_or_after(o), first_workday_on_or_after(n)
        models = sorted(m for m in w.plants[p]["models"] if part in w.bom[m])
        out["disruption"] = {"plant": p, "models": models, "part": part, "from_idx": oi, "to_idx_excl": ni,
                             "earliest_same_plant_idx": ni,
                             "summary": f"{part} missing at {p} {iso(oi)} to {iso(ni - 1)}, models {models}"}
    else:
        part, p = res["part"]["id"], res["plant"]["id"]
        sup = res.get("supplier", {}).get("id")
        if inc.get("lot_id"):
            lots = [w.lots[inc["lot_id"]]] if inc["lot_id"] in w.lots else []
        else:
            ws, we = dt("window_start"), dt("window_end")
            lots = [l for l in w.lots.values() if l["part_id"] == part and l["plant_id"] == p
                    and (sup is None or l["supplier_id"] == sup)
                    and l["first_build_date"] <= we.isoformat() and l["last_build_date"] >= ws.isoformat()]
            if lots and not any(l["first_build_date"] == ws.isoformat() and l["last_build_date"] == we.isoformat()
                                for l in lots):
                out["warnings"].append("window does not match a lot exactly; holding every overlapping lot")
        if inc.get("window_start") and "window_start" not in res:
            dt("window_start"), dt("window_end")
        if not lots:
            raise ValueError("no lot matches")
        for l in lots:
            for fld, val in (("part_id", part), ("plant_id", p), ("supplier_id", sup)):
                if val and l[fld] != val:
                    out["warnings"].append(f"{l['lot_id']} {fld}={l[fld]} but text says {val}")
        res["lots"] = lots
    return out
