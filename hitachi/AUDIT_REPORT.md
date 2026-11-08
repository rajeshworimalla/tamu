# Ripple Radar Accuracy Audit

Date: Saturday Nov 7 2026, TAMU Datathon 2026. Scope: the 15 supplied events, the official `submission/action_log.jsonl`, and the planner and extraction code.

## A. Executive verdict

**Correct on the supplied cases, with interpretation risks that cannot be removed without the hidden grader.**

- An independent validator (`audit/independent.py`) was written from the handbook, the CSVs, `events.json` and `enterprise.py` only. Its scope: it starts from its own hand-annotated reading of each event (the `EVENTS` table) and independently recomputes every expected action. It checks planning and execution, not reading; reading is checked separately by `audit/readings_check.py`, which finds the model's readings match these annotations on all 15 events. It does not import or read `tower/`, `analysis/`, `extract.py` or `run.py`. It agrees with the official log on every event: 0 missing, 0 extra, 0 wrong arguments, 0 duplicates.
- A clean run on a fresh enterprise server (port 8001, `out/audit/server`) produced 768 calls, 0 failed. It is identical to the official log, call for call.
- Two robustness defects were found and fixed. A third gap (transfer fallback) was closed. None of them changes the official log.
- This does not guarantee the hidden score. The grader may read the ambiguous rules in section E differently.

## B. Event scorecard

Today is Monday 2027-03-08. "next X" means X in the following calendar week. Counts are expected (independent validator) and actual (log). They are equal for every event.

| Event | Category | Resolved entities and dates | Actions (expected = actual) | Missing | Extra | Violations | Status |
|---|---|---|---|---|---|---|---|
| E-01 | Compound | Outage P_TX 03-19 to 03-22, restart 03-23. Delay CHIP-IVI, SUP-12, P_IN, SH-0190, 03-15 to 03-19 | 14 reschedule, 41 dealer notify, 26 loaners | 0 | 0 | 0 | Verified |
| E-02 | Unconfirmed | Seat material rumor, nothing confirmed | 1 escalate | 0 | 0 | 0 | Verified |
| E-03 | Quality hold | LOT-0130, CHIP-IVI, SUP-06, P_MS, built 02-25 to 03-01 | 1 hold, 37 stop sale (110 VINs), 150 owners | 0 | 0 | 0 | Verified |
| E-04 | Outage | P_KY 03-16 to 03-18 | 9 reschedule, 32 notify, 18 loaners | 0 | 0 | 0 | Verified |
| E-05 | Noise | Dealer brochure question | none | 0 | 0 | 0 | Verified |
| E-06 | Noise | Dealer brochure question | none | 0 | 0 | 0 | Verified |
| E-07 | Noise | Dealer brochure question | none | 0 | 0 | 0 | Verified |
| E-08 | Outage | P_KY 03-24 to 03-25 | 6 reschedule, 25 notify, 15 loaners | 0 | 0 | 0 | Verified |
| E-09 | Delay | CAM-360, SUP-11, P_AL, SH-0256, 03-29 to 04-01 | 4 reschedule, 2 transfer (PO-0442 to P_TX, PO-0444 to P_KY, 04-01), 26 notify, 10 loaners | 0 | 0 | 0 | Verified |
| E-10 | Delay | BATT-60, SUP-18, P_AL, SH-0248, 03-29 to 04-01 | 3 reschedule, 18 notify, 7 loaners | 0 | 0 | 0 | Verified |
| E-11 | Outage | P_MS 03-26 to 03-30 | 6 reschedule, 3 transfer (PO-0259 to P_KY, PO-0260 to P_IN, PO-0261 to P_TX, 03-31), 36 notify, 17 loaners | 0 | 0 | 0 | Verified |
| E-12 | Delay | CAM-360, P_IN, SH-0182, 03-15 to 03-18 | 3 reschedule, 14 notify, 10 loaners | 0 | 0 | 0 | Verified |
| E-13 | Unconfirmed | "something electronic sometime soon", not confirmed | 1 escalate | 0 | 0 | 0 | Verified |
| E-14 | Quality hold | LOT-0017, HARN-B, SUP-07, P_TX, built 02-22 to 02-24 | 1 hold, 36 stop sale (86 VINs), 94 owners | 0 | 0 | 0 | Verified |
| E-15 | Quality hold | LOT-0191, CHIP-IVI, SUP-12, P_IN, built 03-02 to 03-03 | 1 hold, 25 stop sale (40 VINs), 76 owners | 0 | 0 | 0 | Verified |

Affected production orders: E-01 PO-0058 to PO-0063 and PO-0316, 0318, 0319, 0321, 0322, 0324, 0325, 0327. E-04 PO-0139 to PO-0147. E-08 PO-0157 to PO-0162. E-09 PO-0436, 0438, 0439, 0441, 0442, 0444. E-10 PO-0437, 0440, 0443. E-11 PO-0253 to PO-0261. E-12 PO-0316, 0319, 0322.

## C. Action log statistics

| Measure | Value |
|---|---|
| Total calls | 768 |
| Succeeded / failed | 768 / 0 |
| By tool | reschedule 45, transfer 5, dealer.notify 192, assign_loaner 103, stop_sale 98, notify_customer 320, hold_lot 3, escalate 2 |
| By event | E-01 81, E-02 1, E-03 188, E-04 59, E-05 to E-07 0, E-08 46, E-09 42, E-10 28, E-11 62, E-12 27, E-13 1, E-14 131, E-15 102 |
| Duplicate or conflicting calls | 0 |
| Capacity after replay | no plant day above its slots |
| Loaner pools | never over-allocated, no Standard customer given a loaner |
| Dates | all weekdays inside 2027-03-08 to 2027-04-02 |
| Noise and rumor events | 0 write calls |
| Same-plant slot skipped before a transfer | none |

Replay of all 768 calls in a fresh `enterprise.Enterprise`: all succeed, end state consistent.

## D. Defects found and fixed

| # | File, function | Cause | Rule | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | `tower/world.py`, `DateResolver.resolve` | Common wordings were rejected: "Wednesday", "Monday, March 22", "March 22nd", "3/22", "on Friday". A real incident written that way would be escalated instead of handled. | Dates section, event understanding | Normalize commas, ordinal suffixes and leading "on/by/the"; accept m/d(/y); bare weekday means the first upcoming one. A mismatched weekday and date is still refused. | `tests/edge.py`, date wording cases |
| 2 | `tower/world.py`, `World.resolve` | A part named with the supplier's brand in front ("Cobalt 17-inch alloy wheel") did not resolve, because the catalog name inside a longer mention was not checked. Found by a new 40-message stress test (seed 2026): 2 safe misses. | Names section | The "contained" step also matches the catalog name inside the mention, still only when exactly one record matches. | `tests/edge.py`, part name cases |
| 3 | `tower/agents.py`, `Ledger.place` | When every plant building the model was full after the disruption ended, the planner gave up. The policy check then blocked the whole event, so a real outage got zero actions. | Rule 3: transfer "on any day with a free slot" | Transfers still take the earliest day after the disruption first. Only when none exists does the planner fall back to the earliest earlier day at another plant. | `tests/edge.py`, 03-15 to 03-31 outage case |

| 4 | `extract.py`, `extract_event` | When the model tagged a message about a plant outside our network as an outage, validation failed and the message went to a person instead of being ignored. | Rule 7 | When validation fails and the message names only places outside our network and no parts, it is ignored with a code-written reason. | Checked live: "A plant in Kansas lost power today." is now ignored |

Added for explainability, with no change to any decision:

- Every move records the options it rejected and the one it chose (`Ledger.options`). These show under "Options considered" in each action's evidence and in each trace.
- When no compliant slot exists anywhere, the escalation names the build and every plant that builds it. Example: Princeton and Greensboro both down for the whole window leaves PO-0540 (Ranger) with nowhere to go, so the plan is blocked and handed to a person.
- "Download report" on every incident: the trace plus how the AI read it (each attempt, any retry) and the execution result.
- "Try to trick it" tests in the New message dialog: a rumor, a wrong weekday, a plant outside our network, and the impossible case.

After the fixes: the 15 events produce the identical 768 actions, `tests/edge.py` passes 29/29, and the clean server run is identical to the official log.

## E. Remaining risks

1. **"next Tuesday" meaning.** We read "next X" as the following calendar week. If the grader means "this coming X", E-04 would affect PO-0124 to PO-0132 instead. Evidence for our reading: E-01 item 2 only makes sense with the following week, and E-03's "last Monday" matches its lot exactly.
2. **Transfer day.** We transfer on or after the disruption ends. A literal reading of "any day" would put all 5 transfers on 2027-03-08.
3. **Transfer plant on a tie.** We use the `plants.csv` order. Alphabetical order would change 4 transfers (E-09 PO-0442 and PO-0444, E-11 PO-0260 and PO-0261).
4. **Loaners in a compound event.** We rank all of E-01's customers together per dealer. Handling the outage first, then the delay, would change two loaners (D20 and D45).
5. **Rumor plus real incident in one message.** Fixed: the real incident is handled and the rumor part gets one escalation (`tests/edge.py`). Whether the grader wants that escalation is unknown. None of the 15 events has this pattern.
6. **Noise sent to a person.** A password-reset request was escalated instead of ignored in 2 of 40 stress messages. That is safe, but it costs a needless escalate.
7. **Re-running against a used server.** The server keeps state per event ID. Moves are refused on a second run, but notices would be sent again. Always start the server with `--overwrite` and a fresh `--out` for each run.
8. **Server unreachable mid-run.** Fixed: `run.py` stops at once and names the event and call. Tested by killing the server mid-run: it stopped at E-03 call 40 of 188 with 121 calls logged, as expected. The call in flight may or may not have been applied, so a new run must use a fresh server.

## F. Submission readiness

| Deliverable | State |
|---|---|
| Source code | `hitachi/` |
| Official action log | `submission/action_log.jsonl`, 768 calls, verified |
| Ontology / graph export | `submission/ontology/`: `ontology.json`, `ontology.mmd`, `graph.json` (loads in NetworkX: 17,772 nodes, 31,559 edges) |
| One trace per event | `submission/traces/E-01` to `E-15`, as JSON and Markdown, from a fresh replay identical to the official log, including the server's responses |
| One-page design card | `submission/design_card.pdf` (1 page; source `docs/design_card.html`) |
| Model citation | `submission/model_citation.md`: Qwen2.5-3B-Instruct, `qwen2.5:3b`, Ollama 0.40.15, Qwen Research License |
| Demo | Two-minute video on the Devpost page; 12 app screenshots in `submission/screenshots/`. |
| Reproducible setup | `hitachi/README.md` and `hitachi/requirements.txt`, tested in a fresh virtual environment |

