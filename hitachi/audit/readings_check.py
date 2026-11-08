import ast
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TRACES = os.path.join(HERE, "..", "submission", "traces")
KIND = {"delay": "supplier_delay", "outage": "plant_outage", "quality": "quality_hold", "noise": "noise", "unconfirmed": "unconfirmed"}
FIELDS = (("plant", "plant"), ("part", "part"), ("shipment", "shipment"), ("orig_eta", "original_eta"), ("new_eta", "new_eta"),
          ("start", "start"), ("end", "end"), ("lot", "lot"))


def annotations():
    """Reads the validator's EVENTS table as a pure literal; no code is executed."""
    src = open(os.path.join(HERE, "independent.py"), encoding="utf-8").read()
    start = src.index("EVENTS = ") + len("EVENTS = ")
    return ast.literal_eval(src[start:src.index("\n}\n", start) + 2])


def expected(event):
    items = event["incidents"] if event["kind"] == "compound" else [event]
    out = [{"kind": KIND[i["kind"]], **{b: i[a] for a, b in FIELDS if a in i}} for i in items]
    return sorted(out, key=lambda x: (x["kind"], x.get("plant", "")))


def read(trace):
    out = []
    for inc in trace["incidents"]:
        res, row = inc["resolution"], {"kind": inc["kind"]}
        for f in ("plant", "part"):
            if f in res:
                row[f] = res[f]["id"]
        if "shipment" in res:
            row["shipment"] = res["shipment"]["shipment_id"]
        for f in ("original_eta", "new_eta", "start", "end"):
            if f in res:
                row[f] = res[f]["date"]
        if "lots" in res:
            row["lot"] = res["lots"][0]["lot_id"]
        out.append(row)
    return sorted(out, key=lambda x: (x["kind"], x.get("plant", "")))


def main():
    report, ok = {}, 0
    for eid, event in sorted(annotations().items()):
        trace = json.load(open(os.path.join(TRACES, f"{eid}.json"), encoding="utf-8"))
        want, got = expected(event), read(trace)
        same = len(want) == len(got) and all({k: g.get(k) for k in w} == w for w, g in zip(want, got))
        ok += same
        report[eid] = {"match": same, "read_by": trace["interpretation"]["handled_by"], "model": trace["interpretation"]["model"],
                       "auditor": want, "model_reading": got}
        print(f"{eid}  {'match' if same else 'DIFF '}  read by {trace['interpretation']['model']}")
    json.dump(report, open(os.path.join(HERE, "readings_check.json"), "w", encoding="utf-8"), indent=1)
    print(f"\n{ok}/{len(report)} events: the model's reading, resolved by code, matches the auditor's annotation")


if __name__ == "__main__":
    main()
