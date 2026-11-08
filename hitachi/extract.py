"""Reads messages with the local model and verifies every value against the message and the data."""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request

from tower.types import REAL_KINDS, Kind
from tower.world import DATA, DateResolver, World, resolve_incident

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = (Kind.SUPPLIER_DELAY, Kind.PLANT_OUTAGE, Kind.QUALITY_HOLD, Kind.NOISE, Kind.UNCONFIRMED)
REQUIRED = {
    Kind.SUPPLIER_DELAY: ("plant", "part", "original_eta", "new_eta"),
    Kind.PLANT_OUTAGE: ("plant", "start", "end"),
    Kind.QUALITY_HOLD: ("plant", "part"),
    Kind.NOISE: ("reason",),
    Kind.UNCONFIRMED: ("reason",),
}

SYSTEM = """You read operations messages for Wacky Wheels Co., a carmaker. Today is Monday 2027-03-08.
Split the message into incidents and return JSON: {"incidents": [ ... ]}.

Incident kinds and fields:
- supplier_delay: a part shipment will arrive late.
  {"kind","supplier","part","plant","original_eta","new_eta","shipment_id"?,"evidence"}
- plant_outage: a plant cannot build for a range of days.
  {"kind","plant","start","end","evidence"}
- quality_hold: a lot of a part is defective.
  {"kind","supplier","part","plant","window_start","window_end","lot_id"?,"evidence"}
- noise: not about production, parts, plants or quality. {"kind","reason"}
- unconfirmed: might be about operations but is a rumor, unconfirmed, or missing the part, plant or dates. {"kind","reason"}

Rules:
- Copy names and dates exactly as written in the message ("next Friday", "the Texas plant", "Monday Mar 22"). Never convert or guess.
- Every value you return must appear word for word in the message. If an id is written in parentheses, like (P_NC), you may copy the id.
- The supplier is the company that makes the part, never the carrier or trucking company.
- Include shipment_id or lot_id only if the message states one.
- One message can hold several incidents; return each one.
- Always return at least one incident. A message that is not about operations is one noise incident.
- "evidence" is the exact sentence that supports the incident.
- If any required detail is missing or the report is not confirmed, use unconfirmed.

Example message: "Two things. The Greensboro line is down tomorrow through Friday. Also Vega says the brake modules for Greensboro due Monday Mar 15 now arrive Wednesday Mar 17."
Example answer: {"incidents": [
 {"kind": "plant_outage", "plant": "Greensboro", "start": "tomorrow", "end": "Friday", "evidence": "The Greensboro line is down tomorrow through Friday."},
 {"kind": "supplier_delay", "supplier": "Vega", "part": "brake modules", "plant": "Greensboro", "original_eta": "Monday Mar 15", "new_eta": "Wednesday Mar 17", "evidence": "Vega says the brake modules for Greensboro due Monday Mar 15 now arrive Wednesday Mar 17."}]}

Example message: "Could someone resend the dealer price list?"
Example answer: {"incidents": [{"kind": "noise", "reason": "Price list request; no operational impact."}]}

Example message: "Heard paint might run short at some point, nobody has confirmed."
Example answer: {"incidents": [{"kind": "unconfirmed", "reason": "Rumor about paint; no part, plant or dates and not confirmed."}]}
Return only the JSON object."""

FIELDS = ("supplier", "part", "plant", "original_eta", "new_eta", "start", "end", "window_start", "window_end",
          "shipment_id", "lot_id", "evidence", "reason")
SCHEMA = {"type": "object", "required": ["incidents"], "properties": {"incidents": {
    "type": "array", "minItems": 1, "items": {"type": "object", "required": ["kind"], "properties": {
        "kind": {"type": "string", "enum": list(KINDS)}, **{f: {"type": "string"} for f in FIELDS}}}}}}
GROUNDED = FIELDS[:-2]
OPTIONAL = ("supplier", "shipment_id", "lot_id")
PLACEHOLDERS = {"", "unknown", "n/a", "na", "none", "null", "not specified", "not mentioned"}


def post(url, body, headers, timeout=120):
    """JSON POST with a timeout."""
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def parse_json(text):
    """Model output to JSON, tolerating a code fence."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(t)


def prompt(text, feedback):
    """The message, plus the previous answer and its errors on a retry."""
    if not feedback:
        return text
    return (f"{text}\n\nYour previous answer was {json.dumps(feedback['answer'])} and it was rejected:\n- "
            + "\n- ".join(feedback["errors"]) + "\nCorrect it using only words from the message, and answer again.")


def ask_ollama(text, feedback=None):
    """One schema-constrained, temperature-0 call to the local model."""
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    r = post(os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat",
             {"model": model, "stream": False, "format": SCHEMA, "keep_alive": "30m", "options": {"temperature": 0},
              "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt(text, feedback)}]},
             {}, timeout=300)
    return model, parse_json(r["message"]["content"])


def providers():
    """Readers to try, in order. Local only."""
    return [("ollama", ask_ollama)]


def require_model():
    """Stops with a clear message when Ollama or the model is missing."""
    url, model = os.environ.get("OLLAMA_URL", "http://localhost:11434"), os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as r:
            names = {m["name"] for m in json.loads(r.read()).get("models", [])}
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise SystemExit(f"The language model is not reachable at {url}. Start Ollama (ollama serve) and try again.")
    if model not in names:
        raise SystemExit(f"The model {model} is not installed. Run: ollama pull {model}")
    return model


DATE_FIELDS = ("original_eta", "new_eta", "start", "end", "window_start", "window_end")
DATE_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}|(?:(?:next|last|this)\s+)?(?:mon|tues|wednes|thurs|fri|satur|sun)day(?:\s+[a-z]{3}[a-z]*\.?\s+\d{1,2})?"
                       r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}|tomorrow|today", re.I)
CUES = {Kind.PLANT_OUTAGE: ("down", "dark", "outage", "offline", "shut", "stop", "no builds", "power", "closed", "halt", "idle", "lose", "lost",
                         "fire", "flood", "strike", "maintenance", "can't build", "cannot build", "not building", "no production"),
        Kind.SUPPLIER_DELAY: ("eta", "late", "delay", "can't make it", "cannot make it", "slip", "arriv", "due", "drop", "land", "push",
                           "waiting", "held up", "behind"),
        Kind.QUALITY_HOLD: ("quality", "defect", "faulty", "suspect", "contamina", "crack", "recall", "hold", "bulletin", "bad lot")}
DATES = DateResolver()


def text_dates(text):
    """Every date written in the text."""
    found = set()
    for m in DATE_TEXT.finditer(text):
        try:
            found.add(DATES.resolve(m.group(0))[0])
        except ValueError:
            continue
    return found


def grounded(value, text, field=None):
    """True when the value appears in the message (dates may match by meaning)."""
    norm = lambda s: re.sub(r"\s+", " ", str(s).lower()).strip()
    if norm(value) in norm(text):
        return True
    if field not in DATE_FIELDS:
        return False
    words = set(re.findall(r"[a-z0-9-]+", norm(text)))
    if all(w in words for w in re.findall(r"[a-z0-9-]+", norm(value))):
        return True
    try:
        return DATES.resolve(str(value))[0] in text_dates(text)
    except ValueError:
        return False


def spot(world, etype, text):
    """Records of one type named anywhere in the text."""
    low = f" {re.sub(r'[^a-z0-9_-]+', ' ', text.lower())} "
    found = {}
    for alias, hits in world.aliases.items():
        for t, eid in hits:
            if t == etype and f" {alias} " in low:
                found.setdefault(eid, alias)
    for eid in {"plant": world.plants, "part": world.parts}[etype]:
        if f" {eid.lower()} " in low:
            found.setdefault(eid, eid)
    return found


def clean(world, incidents, text):
    """Drops placeholders and ungrounded ids; fills the plant when exactly one is named."""
    notes = []
    real = [i for i in incidents if isinstance(i, dict) and i.get("kind") in REQUIRED and "plant" in REQUIRED[i["kind"]]] \
        if isinstance(incidents, list) else []
    for inc in incidents if isinstance(incidents, list) else []:
        if not isinstance(inc, dict):
            continue
        for f in list(inc):
            v = inc[f]
            if f in DATE_FIELDS and isinstance(v, str):
                v = inc[f] = re.sub(r"\s*\(.*?\)\s*|[.;,]+$", "", v).strip()
            if isinstance(v, str) and v.strip().lower() in PLACEHOLDERS:
                del inc[f]
            elif f in OPTIONAL and not grounded(v, text):
                notes.append(f"dropped {f} {v!r}, not in the message")
                del inc[f]
    if len(real) == 1 and not real[0].get("plant"):
        plants = spot(world, "plant", text)
        if len(plants) == 1:
            eid, said = plants.popitem()
            real[0]["plant"] = eid if said == eid else next(m.group(0) for m in [re.search(re.escape(said), text, re.I)])
            notes.append(f"plant filled by code from the only plant named in the message: {real[0]['plant']!r}")
    return notes


STATES = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
          "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
          "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
          "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
          "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
          "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
          "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
          "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
          "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
          "wisconsin": "WI", "wyoming": "WY"}
PART_WORDS = r"\b(chips?|semiconductors?|batter(y|ies)|tires?|rims?|wheels?|seats?|harness(es)?|wiring|displays?|screens?|cameras?|brakes?|airbags?|doors?|parts?)\b"
TROUBLE = sum(CUES.values(), ()) + ("accident", "fire", "flood", "storm", "strike", "shortage", "closure", "crash", "spill", "explosion")


def ours(world, text):
    """Plants, parts and suppliers of ours named in the text."""
    low = f" {re.sub(r'[^a-z0-9_-]+', ' ', text.lower())} "
    found = [f"{world.plants[p]['city'].split(',')[0]} plant ({p})" for p in spot(world, "plant", text)]
    found += [world.parts[p]["name"] for p in spot(world, "part", text)]
    found += sorted({world.suppliers[e]["name"] for a, hits in world.aliases.items() for t, e in hits
                     if t == "supplier" and f" {a} " in low})
    return found


def outside(world, text):
    """States named in the text where we have no plant, supplier or dealer."""
    network = {c["city"].rsplit(", ", 1)[-1] for t in (world.plants, world.suppliers, world.dealers) for c in t.values()}
    return sorted(s.title() for s, ab in STATES.items() if re.search(rf"\b{s}\b", text.lower()) and ab not in network)


def explain(world, text, kind):
    """Code-written reason for noise or a rumor."""
    mine, far = ours(world, text), outside(world, text)
    if kind == Kind.UNCONFIRMED:
        gaps = [g for g, ok in (("which part or shipment", any(m in mine for m in (world.parts[p]["name"] for p in world.parts))),
                                ("when", bool(text_dates(text)))) if not ok]
        if mine:
            what = f"doesn't say {' or '.join(gaps)}" if gaps else "isn't confirmed"
            return f"Mentions {', '.join(mine)}, but {what}. It could affect us, so a person should confirm before anything changes."
        return "Sounds like it could affect operations, but names no plant, part, supplier or dates we can check. A person should confirm."
    if far and not mine:
        return f"{', '.join(far)} is outside our network: no Wacky Wheels plant, supplier or dealer there."
    if mine:
        return f"Mentions {', '.join(mine)}, but reports no outage, delay or quality problem."
    return "Not about our plants, parts, suppliers or quality, so nothing changes."


def settle(world, incidents, text):
    """Corrects noise versus rumor using our network, and replaces the model's reason with code's."""
    notes = []
    for inc in incidents:
        if inc.get("kind") == Kind.NOISE and ours(world, text) and any(c in text.lower() for c in TROUBLE):
            inc["kind"] = Kind.UNCONFIRMED
            notes.append("noise upgraded to escalation: names our network and sounds like trouble")
        elif inc.get("kind") == Kind.UNCONFIRMED and outside(world, text) and not ours(world, text) \
                and not re.search(PART_WORDS, text.lower()):
            inc["kind"] = Kind.NOISE
            notes.append("escalation downgraded to noise: only names places outside our network")
        if inc.get("kind") in (Kind.NOISE, Kind.UNCONFIRMED):
            inc["model_reason"], inc["reason"] = inc.get("reason", ""), explain(world, text, inc["kind"])
    return notes


def scope(inc, text):
    """The sentences about one incident."""
    names = [str(inc[f]).lower() for f in ("plant", "part", "supplier", "lot_id", "shipment_id") if inc.get(f)]
    sents = re.split(r"(?<=[.!?;])\s+|\n", text.lower())
    parts = [" ".join(sents[i:i + 2]) for i, s in enumerate(sents) if any(n in s for n in names)]
    if inc.get("evidence") and grounded(inc["evidence"], text):
        parts.append(str(inc["evidence"]).lower())
    return " ".join(parts) or text.lower()


def together(inc, text):
    """In a numbered digest, the plant and its dates must come from the same item."""
    items = [s for s in re.split(r"\(\d+\)|\n\s*\n|\b(?:also|separately)\b", text, flags=re.I) if s.strip()]
    if len(items) < 2 or not inc.get("plant"):
        return True
    when = [inc[f] for f in DATE_FIELDS if inc.get(f)]
    for item in items:
        if str(inc["plant"]).lower() not in item.lower():
            continue
        found = text_dates(item)
        if not when or any(str(v).lower() in item.lower() or DATES.resolve(str(v))[0] in found for v in when):
            return True
    return False


def validate(world, dates, incidents, text):
    """Every check a reading must pass before planning; returns the errors."""
    errors = []
    for i, inc in enumerate(incidents if isinstance(incidents, list) else []):
        for f in GROUNDED:
            if isinstance(inc, dict) and inc.get(f) and not grounded(inc[f], text, f):
                errors.append(f"#{i} {f} {inc[f]!r} does not appear in the message")
    if errors:
        return errors
    if not isinstance(incidents, list) or not incidents:
        return ["no incidents returned"]
    for i, inc in enumerate(incidents):
        kind = inc.get("kind") if isinstance(inc, dict) else None
        if kind not in KINDS:
            errors.append(f"#{i} unknown kind {kind!r}")
            continue
        try:
            apart = kind in CUES and not together(inc, text)
        except ValueError:
            apart = False
        if apart:
            errors.append(f"#{i} the plant {inc['plant']!r} and these dates come from different items in the message")
            continue
        if kind in CUES and not any(c in scope(inc, text) for c in CUES[kind]):
            errors.append(f"#{i} the message never talks like a {kind.replace('_', ' ')}; check the incident kind")
            continue
        missing = [f for f in REQUIRED[kind] if not inc.get(f)]
        if kind == Kind.QUALITY_HOLD and not inc.get("lot_id") and not (inc.get("window_start") and inc.get("window_end")):
            missing.append("window_start/window_end or lot_id")
        if missing:
            errors.append(f"#{i} {kind} missing {missing}")
            continue
        try:
            resolve_incident(world, dates, inc)
        except (ValueError, KeyError) as e:
            errors.append(f"#{i} {kind}: {e}")
    if len(incidents) > 1 and any(x.get("kind") in (Kind.NOISE, Kind.UNCONFIRMED) for x in incidents) \
            and not any(x.get("kind") in REAL_KINDS for x in incidents):
        errors.append("noise or unconfirmed mixed with other incidents")
    return errors


def extract_event(world, dates, event, chain, retries=1):
    """Reads one event with one retry; a reading that still fails becomes a review."""
    attempts, text = [], event["text"]
    for name, ask in chain:
        feedback = None
        for _ in range(retries + 1):
            start, notes = time.perf_counter(), []
            try:
                model, out = ask(text, feedback)
                incidents = out.get("incidents") if isinstance(out, dict) else None
                answer = json.loads(json.dumps(incidents))
                notes = clean(world, incidents, text)
                errors = validate(world, dates, incidents, text)
            except (urllib.error.URLError, TimeoutError) as e:
                model, incidents, errors = None, None, [f"{name} model not reachable ({getattr(e, 'reason', e)})"]
            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                model, incidents, errors = None, None, [f"{name} returned an unreadable answer ({type(e).__name__})"]
            attempts.append({"provider": name, "model": model, "ms": round((time.perf_counter() - start) * 1000),
                             "retry": feedback is not None, "errors": errors, "notes": notes})
            if not errors:
                attempts[-1]["notes"] += settle(world, incidents, text)
                return {"incidents": incidents, "handled_by": name, "model": model, "attempts": attempts}
            if model is None:
                break
            feedback = {"answer": answer, "errors": errors}
    reason = "extraction could not be validated: " + "; ".join(dict.fromkeys(e for a in attempts for e in a["errors"]))
    if outside(world, text) and not ours(world, text) and not re.search(PART_WORDS, text.lower()):
        return {"incidents": [{"kind": Kind.NOISE, "reason": explain(world, text, Kind.NOISE)}], "handled_by": "ignored",
                "model": None, "attempts": attempts}
    return {"incidents": [{"kind": Kind.UNCONFIRMED, "reason": reason}], "handled_by": "escalated",
            "model": None, "attempts": attempts}


def fingerprint(world, dates, incidents):
    """Resolved reading in comparable form."""
    out = []
    for inc in incidents:
        r = resolve_incident(world, dates, inc)
        res = r["resolution"]
        key = {"kind": r["kind"]}
        for f in ("plant", "part"):
            if f in res:
                key[f] = res[f]["id"]
        for f in ("start", "end", "original_eta", "new_eta"):
            if f in res:
                key[f] = res[f]["date"]
        if "shipment" in res:
            key["shipment"] = res["shipment"]["shipment_id"]
        if "lots" in res:
            key["lots"] = sorted(l["lot_id"] for l in res["lots"])
        out.append(key)
    return sorted(out, key=lambda k: json.dumps(k, sort_keys=True))


def check(world, dates, results):
    """Compares readings with the hand-written fixture."""
    ref = json.load(open(os.path.join(HERE, "tests", "fixtures", "reference_readings.json"), encoding="utf-8"))["events"]
    ok = 0
    for eid, r in results.items():
        same = fingerprint(world, dates, r["incidents"]) == fingerprint(world, dates, ref[eid])
        ok += same
        print(f"{eid}  {'OK  ' if same else 'DIFF'}  {r['handled_by']:<10} {r['model'] or '-'}")
        if not same:
            print("   got:", fingerprint(world, dates, r["incidents"]))
            print("   ref:", fingerprint(world, dates, ref[eid]))
    print(f"\n{ok}/{len(results)} events match the reference extraction")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=os.path.join(DATA, "events.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "out", "extraction.json"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    chain = providers()
    world, dates = World(DATA), DateResolver()
    events = json.load(open(args.events, encoding="utf-8"))
    results = {}
    for ev in events:
        if args.only and ev["event_id"] not in args.only:
            continue
        results[ev["event_id"]] = extract_event(world, dates, ev, chain)
        r = results[ev["event_id"]]
        print(f"{ev['event_id']}  {r['handled_by']:<10} {[i['kind'] for i in r['incidents']]}")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2)
    if args.check:
        print()
        check(world, dates, results)


if __name__ == "__main__":
    main()
