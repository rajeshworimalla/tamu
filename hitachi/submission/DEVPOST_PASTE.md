# Devpost fields, ready to paste

Paste each block into the matching Devpost field. The story uses no tables, because Devpost does not render them.

## Project name

Ripple Radar

## Elevator pitch (under 200 characters)

A carmaker control tower where a 3B local model only reads the messages and a knowledge graph decides what to do. 15 events, 768 calls, 0 failures.

## Built with

python, fastapi, networkx, ollama, qwen2.5, d3.js, cytoscape.js, javascript

## Try it out links

- https://github.com/rajeshworimalla/tamu (folder `hitachi/`)
- Demo video: (paste the YouTube or Drive link once uploaded)

## Challenges to opt into

Hitachi only. We did not use Gemini, MongoDB, Snowflake or the other sponsor tools, so we are not opting into those.

## Project story (paste everything below this line)

---

Ripple Radar handled all 15 events with **768 enterprise calls and no failures**. A validator we wrote separately, which shares no code with the planner, agrees with every one of those calls.

The interesting part is how little we trust the language model. It reads each message and that's all. Every order, dealer, car and slot in a tool call comes from walking the company's knowledge graph, so a model mistake is built to end in review rather than a wrong action.

## Inspiration

Wacky Wheels builds just in time, so there are no spare parts sitting around. When one camera shipment for Huntsville slips three days, six builds can't run. Fifty-four customer orders are suddenly late, twenty-six dealers need to hear about it, and somebody has to decide which ten customers get the loaner cars. The news arrives as a two-line supplier email that says "the surround-view cameras run" instead of a part number.

We wanted to see how far a small model running on a laptop could go if we were strict about what it was allowed to decide.

## What it does

Ripple Radar watches the event feed and sorts every message into a supplier delay, a plant outage, a quality hold, a compound of several of those, a rumor, or noise.

For a real incident it works out exactly what is affected: the builds that need the part at that plant in that window, the customer orders promised from those builds, and their dealers and customers. Four agents then plan the recovery under the handbook:

- **Supply Chain Planner** moves each build to the earliest open slot and transfers it only when its own plant is full.
- **Dealer and Customer Care** sends one notice per dealer and hands out loaners by tier and promise date until each dealer's pool runs out.
- **Quality** holds bad lots, stops the sale of affected cars still on lots and contacts owners who already bought one.
- **Coordinator** splits compound messages, decides who gets involved and escalates rumors to a person.

Before anything is sent, a rulebook recomputes all ten handbook rules from the raw tables and replays every call on a private copy of the enterprise system. Then the calls go out, and each one is recorded with the graph path that justifies it.

On the 15 supplied events that came to 50 builds moved (5 of them to other plants), 192 dealer notices, 103 loaners, 3 lots held, 236 cars stopped from sale and 320 owners contacted. The two rumors went to a person and the three noise messages produced no calls at all.

The app is what an operations analyst would open in the morning: the day's figures, an incident queue with the items needing review on top, a map of where the ripple goes, the graph traversal, a before-and-after recovery timeline, and a record explorer for any customer, order or car. You can also type a new message, watch the model read it, check the plan and send it to an enterprise server.

## How we built it

The model is **Qwen2.5 3B** running in Ollama on the laptop, called with a JSON schema at temperature 0. We kept the prompt short and gave it three worked examples.

Everything after reading is Python. The company data becomes a NetworkX graph with 14 kinds of node (supplier, shipment, part, model, plant, build, customer order, customer, dealer, vehicle, lot, plus event, action and rule) and 27 kinds of edge. The agents call four traversals on it: delays, outages, the orders waiting on a build, and lots. The rulebook deliberately doesn't use the graph, so the two can catch each other's mistakes.

The web app is FastAPI with plain JavaScript modules, d3 for the map and timeline, and cytoscape for the graph. There's no build step, no cloud and no API key.

## Challenges we ran into

On our first pass the model read 7 of the 15 events correctly. Later, our generated stress messages caught it copying dates from the wrong item in a numbered digest and calling a supplier delay a plant outage. We didn't switch to a bigger model. Instead we made every one of those mistakes detectable: values have to appear in the message, names have to resolve to a real record, the wording has to match the incident type, and a digest item's plant and dates have to come from the same item. When a check fails, the model gets one retry with the exact error. After that it read 15 of 15, and when it still gets something wrong, the message goes to review.

It still makes mistakes, which we're glad to be able to show. In the official run it named "Carrier", the trucking company, as the supplier for E-09. That name matches no supplier, so it was ignored and the real one came from the shipment record. In E-10 it made up a shipment id that the message never mentioned, and that was dropped before planning.

"Next Friday" was harder than it sounds, because people use it to mean both this week and next week. The data settled it for us. Item 2 of E-01 only matches a real shipment if "next Friday" means the following week, and E-03's "last Monday" only lines up with its part lot on the same convention.

Some of the handbook genuinely leaves room. It says a build can go to another plant "on any day with a free slot", and we read that as the first free day after the disruption ends. We measured what the other reading would change: exactly 5 of our 768 calls, and only their dates. We kept one consistent reading instead of guessing at the grader.

The live demo failed the first time we tried it. The organizer's server only accepts events it already knows, so all 15 calls were refused, and our app reported "0 of 15 accepted" instead of claiming success. We were happier about that than about the bug. The fix was a small demo event feed, which the server supports.

## Accomplishments that we're proud of

Every action in the log can be traced. The 15 trace files cite 1,159 graph paths, one for each record touched, and a test checks that every step of every path is a real edge in the graph.

A plain run with no special flags has the model read every event and reproduces the official log call for call on a fresh server. We also checked the readings against a second set of hand-made answers, and all 15 match.

We also like that the system knows when there's nothing compliant to do. If two plants were down for the whole month, one Ranger build would have nowhere to go. Ripple Radar says so, names the build and stops instead of inventing a slot.

## What we learned

How much you can trust an AI agent depends far more on what checks its output than on how big the model is. The knowledge graph turned out to be the right place for those checks, because "the shipment carries this part to this plant" is either an edge in the data or it isn't.

We also learned to measure our own weak spots before a judge does. Of 240 generated test messages, 221 were read as expected and 19 went to a person rather than being handled. That test checks readings, not executed plans. That's the price of refusing to guess, and we think it's the right one.

## What's next for Ripple Radar

We want two small local models to agree before anything is acted on, and a what-if mode that plays a disruption against a copy of the schedule before it happens. After that comes swapping the simulator for real MES and CRM connections, with the authentication and durable job tracking a real plant would need.

## Where judges can find things

All files are in `hitachi/submission/` in the repository.

- **Event handling accuracy (50%):** `action_log.jsonl` (768 lines, written by the enterprise server, not edited), checked by `audit/independent.py`
- **Knowledge graph and reasoning (20%):** `ontology/ontology_overview.png`, the full `ontology/ontology.png`, and the Graph evidence block in each `traces/E-xx.md`
- **Agents and guardrails (10%):** `design_card.pdf`, and sections 4 to 7 of `DOCUMENTATION.md`
- **Efficiency (10%):** 768 calls, none failed or wasted; Qwen2.5 3B local at about 2.6 seconds per message (`model_citation.md`)
- **Experience and explainability (10%):** `screenshots/`, the demo video, and Download report on any incident

These results are measured against our own validator and the enterprise simulator, not the hidden grader.
