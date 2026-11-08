import argparse
import json
import os
import random
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import extract
from tower.world import DATA, LAST_IDX, TODAY, DateResolver, World, date_to_idx, idx_to_date

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = ("supplier_delay", "plant_outage", "quality_hold")


def say(d, style):
    if style == "iso":
        return d.isoformat()
    if style == "short":
        return f"{d:%b} {d.day}"
    monday = TODAY - timedelta(days=TODAY.weekday())
    if style == "next" and 7 <= (d - monday).days < 14:
        return f"next {d:%A}"
    if style == "this" and 0 < (d - TODAY).days and (d - monday).days < 7:
        return f"this {d:%A}"
    if style == "tomorrow" and d == TODAY + timedelta(days=1):
        return "tomorrow"
    if style == "last" and -7 <= (d - monday).days < 0:
        return f"last {d:%A}"
    return f"{d:%A} {d:%b} {d.day}"


class Cases:
    def __init__(self, w, seed):
        self.w, self.r = w, random.Random(seed)
        self.alias = {}
        for a, hits in w.aliases.items():
            for t, eid in hits:
                self.alias.setdefault((t, eid), []).append(a)

    def plant(self, pid):
        city = self.w.plants[pid]["city"].split(",")[0]
        forms = [city, f"the {city} plant", f"Wacky Wheels {city} ({pid})"] + \
            [a for a in self.alias.get(("plant", pid), []) if a.startswith("the ")]
        return self.r.choice(forms)

    def part(self, pid):
        return self.r.choice(self.alias.get(("part", pid), []) + [self.w.parts[pid]["name"]])

    def supplier(self, sid):
        return self.r.choice([self.w.suppliers[sid]["name"].split()[0], self.w.suppliers[sid]["name"]])

    def delay(self):
        ships = [s for s in self.w.shipments.values() if 1 <= date_to_idx(date.fromisoformat(s["eta_date"])) <= LAST_IDX - 1]
        s = self.r.choice(ships)
        o = date.fromisoformat(s["eta_date"])
        n = idx_to_date(min(LAST_IDX, date_to_idx(o) + self.r.randint(1, 4)))
        os_, ns = say(o, self.r.choice(["abs", "abs", "next", "iso", "short"])), say(n, self.r.choice(["abs", "abs", "next", "iso"]))
        sup, part, plant = self.supplier(s["supplier_id"]), self.part(s["part_id"]), self.plant(s["plant_id"])
        text = self.r.choice([
            f"Heads up from {sup}: the {part} run for {plant} can't make it {os_}. New ETA {ns} (driver shortage).",
            f"{plant} line is waiting on {part} from {sup}. Original drop was {os_}, new ETA is {ns}.",
            f"Subject: delay notice\n{sup} shipment of {part} for {plant}, due {os_}, now arriving {ns}. Reason: customs hold.",
            f"Carrier RoadRunner Freight says the {sup} {part} headed to {plant} slips from {os_} to {ns}."])
        return text, [{"kind": "supplier_delay", "plant": s["plant_id"], "part": s["part_id"],
                       "original_eta": o.isoformat(), "new_eta": n.isoformat()}]

    def outage_spec(self, avoid=None):
        pid = self.r.choice([p for p in self.w.plants if p != avoid])
        a = self.r.randint(1, LAST_IDX - 3)
        b = min(LAST_IDX - 1, a + self.r.randint(0, 3))
        s, e = idx_to_date(a), idx_to_date(b)
        styles = ["abs", "abs", "next", "this", "tomorrow", "iso", "short"]
        return pid, s, e, say(s, self.r.choice(styles)), say(e, self.r.choice(styles))

    def outage(self):
        pid, s, e, ss, es = self.outage_spec()
        plant = self.plant(pid)
        cause = self.r.choice(["a power failure", "a software outage", "a flooded paint shop", "a fire inspection"])
        text = self.r.choice([
            f"{plant} update: {cause}. We're dark from {ss} through {es}; the line restarts the following working day.",
            f"Plant alert: {plant} stops production {ss} to {es} because of {cause}.",
            f"No builds at {plant} from {ss} until {es} inclusive, {cause}."])
        return text, [{"kind": "plant_outage", "plant": pid, "start": s.isoformat(), "end": e.isoformat()}]

    def quality(self):
        lot = self.r.choice(list(self.w.lots.values()))
        f, l = date.fromisoformat(lot["first_build_date"]), date.fromisoformat(lot["last_build_date"])
        sup, part, plant = self.supplier(lot["supplier_id"]), self.part(lot["part_id"]), self.plant(lot["plant_id"])
        fs, ls = say(f, self.r.choice(["abs", "last", "short"])), say(l, self.r.choice(["abs", "last", "iso"]))
        defect = self.r.choice(["a faulty weld", "moisture contamination", "a cracked housing", "a firmware defect"])
        text = self.r.choice([
            f"Quality alert: {sup} says the {part} sent to {plant} had {defect}. Anything built {fs} through {ls} is suspect.",
            f"QUALITY BULLETIN: Lot {lot['lot_id']} ({lot['part_id']}, supplier {lot['supplier_id']}) installed at {lot['plant_id']} on vehicles built {f} to {l} has {defect}."])
        return text, [{"kind": "quality_hold", "plant": lot["plant_id"], "part": lot["part_id"],
                       "supplier": lot["supplier_id"], "lot_id": lot["lot_id"]}]

    def noise(self):
        city = self.r.choice([p["city"] for p in self.w.plants.values()] + [d["city"] for d in self.w.dealers.values()])
        part = self.r.choice(["airbag", "battery", "infotainment"])
        text = self.r.choice([
            f"Dealer {city} asks where to find the new brochure PDF.",
            f"Reminder: the {city} office holiday party is moved to Friday.",
            f"Industry news: a rival carmaker recalls 40,000 SUVs over {part} faults. None of our vehicles are affected.",
            "Can someone reset my password for the dealer portal?",
            "Weather service: heavy snow expected in Montana this weekend.",
            "Marketing wants new photos of the Voyager for the spring campaign."])
        return text, [{"kind": "noise"}]

    def rumor(self):
        plant = self.plant(self.r.choice(list(self.w.plants)))
        text = self.r.choice([
            "Someone on the floor heard a supplier might be running late on something. Nothing confirmed.",
            f"Rumor that {plant} could have some downtime at some point. No dates, nobody has confirmed it.",
            "A rep mentioned possible quality issues with some seats. No details.",
            "Hearing chatter about a chip shortage later this spring, nothing official."])
        return text, [{"kind": "unconfirmed"}]

    def compound(self):
        t1, e1 = self.outage()
        t2, e2 = self.delay()
        if e1[0]["plant"] == e2[0]["plant"]:
            return self.compound()
        return f"Morning digest, two items. (1) {t1} (2) {t2}", e1 + e2


def fingerprint(w, dr, incidents):
    try:
        return extract.fingerprint(w, dr, incidents)
    except (ValueError, KeyError) as e:
        return [{"error": str(e)}]


def grade(exp_fp, got, got_fp):
    exp_real = any(x["kind"] in REAL for x in exp_fp)
    got_real = any(x.get("kind") in REAL for x in got)
    if got_fp == exp_fp:
        return "correct"
    if not exp_real and not got_real:
        return "minor"
    if exp_real and not got_real:
        return "safe miss"
    return "WRONG"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    w, dr = World(DATA), DateResolver()
    gen = Cases(w, args.seed)
    mix = ["delay"] * 10 + ["outage"] * 8 + ["quality"] * 7 + ["noise"] * 6 + ["rumor"] * 5 + ["compound"] * 4
    chain, results, tally = extract.providers(), [], {}
    for i, k in enumerate((mix * (args.n // len(mix) + 1))[:args.n]):
        text, expected = getattr(gen, k)()
        t = time.perf_counter()
        r = extract.extract_event(w, dr, {"event_id": f"S-{i:02d}", "text": text}, chain)
        exp_fp, got_fp = fingerprint(w, dr, expected), fingerprint(w, dr, r["incidents"])
        g = grade(exp_fp, r["incidents"], got_fp)
        tally[g] = tally.get(g, 0) + 1
        results.append({"id": f"S-{i:02d}", "type": k, "grade": g, "text": text, "expected": exp_fp, "got": got_fp,
                        "seconds": round(time.perf_counter() - t, 1), "attempts": r.get("attempts")})
        print(f"S-{i:02d} {k:<9} {g:<10} {results[-1]['seconds']:>4}s  {text[:90]!r}")
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    json.dump(results, open(os.path.join(HERE, "out", f"stress_{args.seed}.json"), "w", encoding="utf-8"), indent=1)
    print("\n" + ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())))


if __name__ == "__main__":
    main()
