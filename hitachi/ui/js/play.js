import { $, $$, ICON, SOURCE, TOOL, esc, eventDetail, highlight, kind, overview, time, title } from "./core.js";
import { createMap } from "./usmap.js";

const CHOICES = [
  { key: "incident", icon: ICON.act, label: "Act", hint: "Confirmed disruption: reschedule, notify, assign loaners.", kbd: "A" },
  { key: "escalated", icon: ICON.escalate, label: "Escalate", hint: "Possibly relevant, but unconfirmed or incomplete.", kbd: "E" },
  { key: "noise", icon: ICON.ignore, label: "Ignore", hint: "Not related to operations.", kbd: "I" },
];
const VERDICT = { incident: "Act", escalated: "Escalate", noise: "Ignore" };
let map, events, i, picks, started, onKey;

function progress() {
  return `<div id="prog" style="display:grid;gap:10px"><div class="progress">${events.map((e, j) => `<i class="${j < picks.length ? (picks[j] === kind(e) ? "right" : "wrong") : j === i ? "now" : ""}"></i>`).join("")}</div>
    <div class="score"><span>Scenario <b>${Math.min(i + 1, events.length)}</b> of ${events.length}</span><span>Matches <b>${picks.filter((p, j) => p === kind(events[j])).length}</b></span></div></div>`;
}

function card(e) {
  return `<article class="msg"><div class="msg-head"><span class="avatar">${SOURCE[e.source] || "?"}</span>
    <div><b>${esc(e.source.replace(/^./, (c) => c.toUpperCase()))}</b><span>${esc(time(e.received_at))} &middot; Monday, March 8</span></div></div>
    <p class="msg-text" id="msgText">${esc(e.text)}</p></article>`;
}

function render() {
  const left = $("#playLeft");
  if (i >= events.length) return finish(left);
  const e = events[i];
  left.innerHTML = `${progress()}${card(e)}<h2 class="ask">Your decision</h2>
    <div class="choices">${CHOICES.map((c) => `<button class="choice" data-k="${c.key}"><span class="ico">${c.icon}</span>
      <span><b>${c.label}</b><span>${c.hint}</span></span><kbd>${c.kbd}</kbd></button>`).join("")}</div><div id="verdict"></div>`;
  $$(".choice", left).forEach((b) => b.onclick = () => answer(b.dataset.k));
  map?.reset();
  $("#caption").innerHTML = "Select a decision.";
}

async function answer(k) {
  if (picks.length > i) return;
  const e = events[i], truth = kind(e), right = k === truth;
  picks.push(k);
  $$(".choice").forEach((b) => {
    b.disabled = true;
    b.classList.toggle("picked", b.dataset.k === k);
    b.classList.toggle("answer", b.dataset.k === truth);
    b.classList.toggle("miss", b.dataset.k === k && !right);
  });
  $("#prog").outerHTML = progress();
  const d = await eventDetail(e.event_id);
  $("#msgText").innerHTML = highlight(d.text, d.incidents);
  const stats = Object.entries(d.counts || {}).map(([t, n]) => `<span class="chip"><b>${n}</b> ${TOOL[t] || t}</span>`).join("");
  $("#verdict").innerHTML = `<div class="verdict"><h3 class="${right ? "good" : "bad"}">${right ? "Match" : "Mismatch"}</h3>
    <table class="read"><tr><td>Your decision</td><td>${VERDICT[k]}</td></tr><tr><td>Ripple Radar</td><td>${VERDICT[truth]}</td></tr>
    <tr><td>Policy result</td><td><b>${esc(title(d.classification))}.</b> ${esc(d.summary)}</td></tr></table>
    ${stats ? `<div class="chips" style="margin-top:10px">${stats}</div>` : ""}
    <div class="cta" style="margin-top:16px"><button class="btn btn-mint" id="next">${i + 1 < events.length ? "Next scenario" : "Results"}</button><span class="faint" style="align-self:center"><kbd>Enter</kbd></span></div></div>`;
  $("#next").onclick = () => { i += 1; render(); };
  $("#next").focus({ preventScroll: true });
  $("#verdict").scrollIntoView({ behavior: "smooth", block: "end" });
  if (truth === "incident") {
    $("#caption").innerHTML = `<b>${esc(title(d.classification))}.</b> Impact across the network.
      <div class="legend"><span><i class="dot" style="background:var(--amber)"></i>Supplier</span><span><i class="dot" style="background:var(--coral)"></i>Disrupted</span><span><i class="dot" style="background:var(--mint)"></i>Handled</span></div>`;
    map?.ripple(d.geo);
  } else {
    map?.reset();
    $("#caption").innerHTML = truth === "noise" ? "No impact. No records changed." : "Sent for review. No records changed.";
  }
}

function finish(left) {
  const score = picks.filter((p, j) => p === kind(events[j])).length, secs = Math.round((performance.now() - started) / 1000);
  const by = ["incident", "escalated", "noise"].map((k) => {
    const idx = events.map((e, j) => (kind(e) === k ? j : -1)).filter((j) => j >= 0);
    return `<span class="chip"><b>${idx.filter((j) => picks[j] === k).length}/${idx.length}</b> ${VERDICT[k].toLowerCase()}</span>`;
  }).join("");
  left.innerHTML = `${progress()}<div class="final"><p class="kicker">Matches</p><div class="big serif">${score}<small> / ${events.length}</small></div><div class="chips" style="justify-content:center;margin-top:16px">${by}</div>
    <p class="muted" style="margin-top:20px">${secs} s for ${events.length} decisions. Ripple Radar planned ${events.reduce((n, e) => n + e.actions, 0).toLocaleString()} actions for the same events, each checked against the policy rules.</p>
    <div class="cta" style="justify-content:center"><a class="btn btn-mint btn-lg" href="#/incidents">Open incidents</a><button class="btn btn-lg" id="again">Restart</button></div></div>`;
  $("#again").onclick = () => start();
  map?.idle();
  $("#caption").innerHTML = "Session complete.";
}

function start() {
  i = 0; picks = []; started = performance.now();
  render();
}

export default {
  async enter(view) {
    view.innerHTML = `<section class="play"><div class="play-left" id="playLeft"><p class="placeholder">Loading events...</p></div>
      <div class="play-right"><div id="playMap" style="position:absolute;inset:0"></div><div class="map-caption" id="caption"></div></div></section>`;
    events = (await overview()).events.filter((e) => !e.event_id.startsWith("LIVE"));
    start();
    createMap($("#playMap")).then((m) => { map = m; });
    onKey = (ev) => {
      if (ev.target.closest("input, textarea, dialog")) return;
      const c = CHOICES.find((x) => x.kbd.toLowerCase() === ev.key.toLowerCase());
      if (c && picks.length === i) answer(c.key);
      else if (ev.key === "Enter" && $("#next")) { ev.preventDefault(); $("#next").click(); }
    };
    window.addEventListener("keydown", onKey);
  },
  leave() { map?.destroy(); map = null; window.removeEventListener("keydown", onKey); },
};
