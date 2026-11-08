# Submit checklist (Devpost deadline Sun Nov 8, 10:30 AM CT)

Devpost shows "Deadline: Nov 8, 2026 @ 10:30am" (11:30 AM Eastern). Aim to press Submit by 10:00 AM. Devpost lets you edit after submitting until the deadline, so submit early and improve after.

## 1. Record the video (about 2:00)

Script: `demo/narration.md`. Shots and clicks: `demo/shot_list.md`. Prep: `demo/checklist.md`.

On this laptop the venv is one folder up, so run these from `C:\dev\tamu\hitachi`.

Terminal 1, the demo enterprise server:

```bash
../.venv/Scripts/python _package/hack_the_highway_package/enterprise_server.py --data _package/hack_the_highway_package/data --events demo/demo_events.json --out runs/demo --port 8001 --overwrite
```

Terminal 2, the app:

```bash
../.venv/Scripts/python -m uvicorn app:app --port 8050
```

Open http://localhost:8050 at 1600x900. Do one dry run of shot 6, then restart both so the recorded run is LIVE-01. Record with Win+Alt+R (Xbox Game Bar) or OBS. Upload to YouTube as Unlisted; Devpost needs a YouTube, Vimeo or Youku link.

If time runs short, the challenge accepts screenshots instead of a video: the 12 in `screenshots/` cover every required screen.

## 2. Fill in Devpost

Copy each field from `DEVPOST_PASTE.md`: name, elevator pitch, story, built with, links.

- Image gallery, in this order: `screenshots/01-operations.png`, `ontology/ontology_overview.png`, `screenshots/03-incident-e09-graph.png`, `screenshots/04-incident-e09-recovery-timeline.png`, `screenshots/05-incident-e09-options-considered.png`, `screenshots/07-incident-e03-quality-hold.png`, `screenshots/12-validation-no-capacity-blocked.png`, `how_it_works.png`
- Challenge: select **Hitachi**.
- Add all 4 teammates to the project.

## 3. Files the challenge requires (all in this folder)

- [x] `action_log.jsonl` from the run on the 15 events (768 lines, 0 failures)
- [x] Source code: the GitHub link, plus `dist/ripple-radar.zip` (111 files, 8 MB) if the portal takes an upload
- [x] Ontology export or diagram: `ontology/`
- [x] A trace for each event: `traces/E-01` to `E-15`, `.md` and `.json`
- [x] Summary and reason for every event: in each trace and in the app
- [x] One-page design card: `design_card.pdf`
- [x] Model citation: `model_citation.md`
- [ ] Demo video link

## Verified on Nov 8, morning

- `tests/edge.py`: 30/30 passed
- `audit/independent.py`: 0 missing, 0 extra, 0 wrong arguments on all 15 events
- Log counts match the write-up: 45 reschedules, 5 transfers, 192 dealer notices, 103 loaners, 3 lot holds, 236 cars stopped from sale (98 calls), 320 owners contacted, 2 escalations
- 1,159 graph paths across the 15 traces
