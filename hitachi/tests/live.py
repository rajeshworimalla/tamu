import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(HERE, "_package", "hack_the_highway_package")
OUT = os.path.join(HERE, "out", "live_test")
PY = sys.executable
OFFICIAL = os.path.join(HERE, "submission", "action_log.jsonl")
DELAY = "Heads up from Lumen: the 60 kWh battery packs for Huntsville due Monday Mar 22 now land Wednesday Mar 24."
OUTAGE = "No builds at the Lexington plant from Tuesday Mar 16 through Thursday Mar 18."
results, procs = [], []


def case(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))


def call(url, body=None):
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def wait(url):
    for _ in range(600):
        try:
            urllib.request.urlopen(url, timeout=5)
            return
        except Exception:
            time.sleep(0.2)
    raise SystemExit(f"{url} did not start")


def server(port, folder, feed=None):
    args = [PY, "-B", "enterprise_server.py", "--data", "data", "--out", folder, "--port", str(port), "--overwrite"]
    procs.append(subprocess.Popen(args + (["--events", feed] if feed else []), cwd=PKG,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    wait(f"http://127.0.0.1:{port}/tools")


def app(port, target):
    env = dict(os.environ, ENTERPRISE_URL=target)
    procs.append(subprocess.Popen([PY, "-B", "-m", "uvicorn", "app:app", "--port", str(port)], cwd=HERE, env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    wait(f"http://127.0.0.1:{port}/")
    return f"http://127.0.0.1:{port}"


def log(folder, eid):
    path = os.path.join(folder, "action_log.jsonl")
    return [r for r in map(json.loads, open(path, encoding="utf-8")) if r["event_id"] == eid] if os.path.exists(path) else []


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    before = hashlib.sha256(open(OFFICIAL, "rb").read()).hexdigest()
    demo, official = os.path.join(OUT, "demo"), os.path.join(OUT, "official_feed")
    try:
        server(8071, demo, os.path.join(HERE, "demo", "demo_events.json"))
        server(8072, official)
        a, b = app(8070, "http://127.0.0.1:8071"), app(8073, "http://127.0.0.1:8072")

        code, d = call(a + "/api/simulate", {"text": DELAY})
        case("new message is read by the model and held as a checked preview",
             code == 200 and d["read_by"] == "ollama" and d["status"] == "verified" and d["actions"], f"{code} {d.get('status')} {d.get('read_by')}")
        eid, planned = d["event_id"], [(x["tool"], x["args"]) for x in d["actions"]]
        code, d = call(a + f"/api/execute/{eid}", {})
        rows = log(demo, eid)
        case("send executes every action and the status turns Resolved",
             code == 200 and d["status"] == "resolved" and d["execution"]["ok"] == len(planned), f"{code} {d.get('status')} {d.get('execution')}")
        case("the demo server received exactly the planned calls, in order, with the same arguments, all accepted",
             [(r["tool"], r["args"]) for r in rows] == planned and all(r["ok"] for r in rows), f"{len(rows)} rows for {len(planned)} planned")
        case("a plan cannot be sent twice", call(a + f"/api/execute/{eid}", {})[0] == 409)
        case("the official events cannot be sent from the app", call(a + "/api/execute/E-09", {})[0] == 400)

        code, d = call(a + "/api/simulate", {"text": DELAY})
        eid3 = d["event_id"]
        with ThreadPoolExecutor(2) as pool:
            codes = sorted(f.result()[0] for f in [pool.submit(call, a + f"/api/execute/{eid3}", {}) for _ in range(2)])
        case("two simultaneous sends of one plan: exactly one is executed, the other is refused",
             codes == [200, 409] and len(log(demo, eid3)) == len(d["actions"]), f"{codes}, {len(log(demo, eid3))} rows")
        case("empty and oversized messages are rejected before reaching the model",
             call(a + "/api/simulate", {"text": ""})[0] == 422 and call(a + "/api/simulate", {"text": "x" * 2001})[0] == 422)
        with urllib.request.urlopen(a + "/") as r:
            sent = r.headers
        case("security headers are set: script sources limited to this server, no framing, no sniffing",
             "script-src 'self'" in sent.get("Content-Security-Policy", "") and sent.get("X-Frame-Options") == "DENY"
             and sent.get("X-Content-Type-Options") == "nosniff")

        code, d = call(a + "/api/simulate", {"text": OUTAGE})
        moves = [x for x in d.get("actions", []) if x["tool"] in ("mes.reschedule", "mes.transfer")]
        case("second message is read and planned with build moves", code == 200 and d["status"] == "verified" and moves,
             f"{code} {d.get('status')} {d.get('read_by')}")
        eid2, n = d["event_id"], len(d["actions"])
        call("http://127.0.0.1:8071/act", {"event_id": eid2, "tool": moves[0]["tool"], "args": moves[0]["args"]})
        code, d = call(a + f"/api/execute/{eid2}", {})
        rows = log(demo, eid2)
        case("a call the server rejects is reported: status Partial, one fewer accepted, the server's reason shown",
             code == 200 and d["status"] == "partial" and d["execution"]["ok"] == n - 1 and "already" in (d["execution"]["error"] or ""),
             f"{code} {d.get('status')} {d.get('execution')}")
        case("the server log shows the rejected call and nothing else lost", len(rows) == n + 1 and sum(not r["ok"] for r in rows) == 1,
             f"{len(rows)} rows, {sum(not r['ok'] for r in rows)} rejected")

        code, d = call(b + "/api/simulate", {"text": DELAY})
        code, d = call(b + f"/api/execute/{d['event_id']}", {})
        case("the app refuses to send to a server running the official event feed", code == 403, f"{code} {d}")
        case("nothing was written to that server", not os.path.exists(os.path.join(official, "action_log.jsonl"))
             or not open(os.path.join(official, "action_log.jsonl")).read().strip())
        case("the official submission log is unchanged", hashlib.sha256(open(OFFICIAL, "rb").read()).hexdigest() == before)
    finally:
        for p in procs:
            p.kill()
    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
