import { $, $$, ICON, RULES, TOOL, api, esc, eventDetail, forget, highlight, overview, pill, time, title } from "./core.js";
import { drawFlow } from "./flow.js";
import { drawTimeline } from "./timeline.js";
import { createMap } from "./usmap.js";

let map, flow, line, current, detail, filter = "all", view = "map", side = "actions", events = [];
const VIEWS = { map: "Impact map", graph: "Graph", timeline: "Recovery timeline" };
const SIDES = { actions: "Actions", explain: "Decision details" };
const node = (id) => `<a href="#/network/${encodeURIComponent(id)}">${esc(id.split(":").pop())}</a>`;

const match = (e, s) => s === "all" || e.status === s || (s === "review" && ["blocked", "partial", "failed"].includes(e.status));

function queue() {
  const n = (s) => events.filter((e) => match(e, s)).length;
  const tabs = [["all", "Total"], ["review", "Review"], ["verified", "Not sent"], ["resolved", "Resolved"], ["ignored", "Ignored"]].filter(([k]) => k !== "verified" || n(k));
  $("#counts").style.gridTemplateColumns = `repeat(${tabs.length}, 1fr)`;
  $("#counts").innerHTML = tabs
    .map(([k, l]) => `<button data-f="${k}" class="${filter === k ? "on" : ""}"><b>${n(k)}</b><span class="label">${l}</span></button>`).join("");
  $$("#counts button").forEach((b) => b.onclick = () => { filter = b.dataset.f; queue(); });
  const list = events.filter((e) => match(e, filter));
  $("#queue").innerHTML = list.map((e) => `<li class="qrow ${e.event_id === current ? "on" : ""}" data-id="${esc(e.event_id)}" tabindex="0">
    <time>${esc(time(e.received_at))}</time><div><div class="top"><span class="title">${esc(title(e.classification))}</span>${pill(e.status)}</div>
    <div class="tag">${esc(e.tagline)}</div><div class="id">${esc(e.event_id)} &middot; ${esc(e.source)}</div></div></li>`).join("") || `<li class="placeholder">Nothing here</li>`;
  $$(".qrow").forEach((el) => { el.onclick = () => select(el.dataset.id); el.onkeydown = (k) => k.key === "Enter" && select(el.dataset.id); });
  $("#queueCount").textContent = `${list.length} OF ${events.length}`;
}

function incident(d) {
  const prov = d.read_by === "ollama" ? `<span class="prov">Read by ${esc(d.model)}</span>`
    : d.read_by === "reference" ? `<span class="prov warn">Reference reading, model not used</span>`
    : `<span class="prov warn">Model reading rejected by checks</span>`;
  const live = d.event_id.startsWith("LIVE");
  const preview = !live ? "" : d.execution ? `<span class="prov">Sent as ${esc(d.execution.server_event_id)}</span>`
    : `<span class="prov warn">Preview, not sent</span>`;
  $("#incident").innerHTML = `<div class="meta">${pill(d.status)}<span class="mono faint">${esc(d.event_id)} &middot; ${esc(time(d.received_at))} &middot; ${esc(d.source.toUpperCase())}</span>${prov}${preview}</div>
    <h2>${esc(title(d.classification))}</h2><p class="msg">${highlight(d.text, d.incidents)}</p>
    <div class="decision"><span class="label">Decision</span><span>${esc(d.summary)}</span></div>`;
  const run = d.execution, n = d.actions.length;
  const said = { resolved: `Done. All <b>${run?.ok ?? n}</b> actions were carried out and accepted by the company systems.`,
    verified: `Ready. ${n} actions passed every check in rehearsal but have <b>not been sent</b> to the company systems yet.`,
    review: "Needs review. No records changed.", ignored: "Not related to operations. No records changed.",
    partial: `Partial. ${run?.ok ?? 0} of ${n} actions were accepted by the company systems. The rest need review.`,
    failed: `Not accepted. The enterprise server refused every call${run?.error ? `: ${esc(run.error)}` : ""}. Nothing changed.`,
    blocked: `Stopped before sending. ${esc(d.actions.find((a) => a.tool === "escalate")?.args.reason || "Needs review.")}` }[d.status];
  const canSend = live && !run && n && ["verified", "review"].includes(d.status);
  $("#footbar").innerHTML = `<span id="footMsg" class="${["blocked", "partial", "failed"].includes(d.status) ? "error" : ""}">${said}</span>
    ${canSend ? `<button class="btn btn-primary send" id="sendLive">Send to enterprise server</button>` : ""}
    <a class="btn report" href="/api/report/${encodeURIComponent(d.event_id)}" download>Download report</a>`;
  if (!canSend) return;
  $("#sendLive").onclick = async () => {
    $("#sendLive").disabled = true;
    $("#sendLive").textContent = "Sending...";
    try {
      await api(`/api/execute/${encodeURIComponent(d.event_id)}`, { method: "POST" });
      forget();
      events = (await overview()).events;
      queue();
      await select(d.event_id);
    } catch (err) {
      $("#footMsg").className = "error";
      $("#footMsg").textContent = err.message;
      $("#sendLive").remove();
    }
  };
}

const fmt = (iso) => { const t = new Date(`${iso}T12:00:00`); return `${t.toLocaleString("en", { month: "short" })} ${t.getDate()}`; };

function trail(d) {
  const by = {};
  d.actions.forEach((a) => ((by[a.agent] ||= {})[a.tool] = ((by[a.agent] ||= {})[a.tool] || 0) + 1));
  const steps = [["Coordinator", "Read the message", `Read by ${d.model || d.read_by} as ${title(d.classification).toLowerCase()}: ${d.tagline}.`]];
  Object.entries(by).filter(([agent]) => agent !== "Coordinator").forEach(([agent, tools]) =>
    steps.push([agent, "Proposed", Object.entries(tools).map(([t, c]) => `${c} ${(TOOL[t] || t).toLowerCase()}`).join(", ")]));
  if (by.Coordinator?.escalate) steps.push(["Coordinator", "Sent for review", "Unconfirmed or incomplete. No records changed."]);
  const ok = d.checks.every((c) => c.ok);
  if (Object.keys(by).some((a) => a !== "Coordinator")) steps.push(["Rulebook", ok ? "Approved" : "Rejected",
    ok ? "Every proposed action was tried on a copy of the company systems and checked against the handbook. All passed."
      : `Failed: ${d.checks.filter((c) => !c.ok).map((c) => `rule ${c.rule}`).join(", ")}.`]);
  const run = d.execution;
  steps.push(["Coordinator", run ? "Sent to the company systems" : ok ? "Not sent yet" : "Blocked", run ? `${run.ok} of ${run.sent} actions accepted.`
    : !ok ? "Nothing was sent. The plan needs review." : d.actions.length ? "The plan passed every check. It has not been executed on the enterprise server." : "Nothing to send."]);
  return `<div class="sect"><div class="label">How the agents handled it</div>${steps.map(([who, what, text], i) =>
    `<div class="story"><h4>${esc(what)} <span class="faint mono">${esc(who)}</span></h4><p>${esc(text)}</p></div>`).join("")}</div>`;
}

function evidence(a) {
  const [rule, text] = RULES[+a.rule - 1] || ["", ""];
  const was = a.before ? `<tr><td>Was</td><td>${esc(a.before.plant)}, ${fmt(a.before.date)}</td></tr><tr><td>Now</td><td>${esc(a.args.to_plant_id || a.before.plant)}, ${fmt(a.args.new_date)}</td></tr>` : "";
  return `<table class="read evid">${was}<tr><td>Proposed by</td><td>${esc(a.agent)}</td></tr><tr><td>Rule</td><td><b>${esc(rule)}</b>. ${esc(text)}</td></tr>
    <tr><td>Server</td><td>${a.executed === true ? "Accepted by the company systems" : a.executed === false ? "Not accepted" : "Not sent yet"}</td></tr></table>
    ${a.alternatives ? `<div class="label opts-h">Options considered</div><table class="read opts">${a.alternatives.map((x) =>
      `<tr class="${x.chosen ? "pick" : ""}"><td>${esc(x.option)}</td><td>${esc(x.verdict)}</td></tr>`).join("")}</table>` : ""}
    <div class="path">${a.path.map(node).join("")}</div>`;
}

function actions(d) {
  if (!d.actions.length) return trail(d);
  const groups = {};
  d.actions.forEach((a, i) => (groups[a.tool] ||= []).push([a, i]));
  const target = (a) => a.args.production_order_id || a.args.lot_id || a.args.dealer_id || a.args.customer_order_id || a.args.customer_id || "";
  const extra = (a) => (a.args.customer_order_ids ? `${a.args.customer_order_ids.length} orders` : a.args.vins ? `${a.args.vins.length} cars` : a.args.new_date ? `to ${fmt(a.args.new_date)}` : "");
  return trail(d) + `<div class="sect"><div class="label">Every action<span>click one for its evidence</span></div>${Object.entries(groups).map(([t, xs]) =>
    `<details class="group"><summary>${TOOL[t] || esc(t)}<span class="n">${xs.length}</span></summary><div class="rows">${xs.map(([a, i]) =>
      `<details class="act" data-i="${i}" data-po="${esc(a.args.production_order_id || "")}"><summary><span class="mono">${esc(target(a))}</span> <span class="faint">${esc(extra(a))}</span>
      <span class="tick-s ${a.executed ? "" : "off"}" title="${a.executed ? "Accepted by the company systems" : "Not sent yet"}">${ICON.ok}</span></summary>
      <div class="why">${esc(a.reason)}</div>${evidence(a)}</details>`).join("")}</div></details>`).join("")}</div>`;
}

function focusAction(po) {
  side = "actions";
  sidePane();
  const el = $(`#sideBody details.act[data-po="${CSS.escape(po)}"]`);
  if (!el) return;
  el.closest("details.group").open = true;
  el.open = true;
  el.scrollIntoView({ block: "center", behavior: "smooth" });
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1600);
}

function explain(d) {
  const reads = d.incidents.map((r) => {
    const rows = Object.entries(r.resolution).filter(([, v]) => v && v.mention).map(([f, v]) =>
      `<tr><td>${esc(f.replace(/_/g, " "))}</td><td>&ldquo;${esc(v.mention)}&rdquo;</td><td><span class="resolved">${esc(v.id || v.date)}</span></td></tr>`);
    if (r.resolution.shipment) rows.push(`<tr><td>shipment</td><td>by part, plant, date</td><td>${node(`Shipment:${r.resolution.shipment.shipment_id}`)}</td></tr>`);
    if (r.resolution.lots) rows.push(`<tr><td>lot</td><td>by part, plant, dates</td><td>${r.resolution.lots.map((l) => node(`Lot:${l.lot_id}`)).join(" ")}</td></tr>`);
    if (!rows.length) rows.push(`<tr><td>reason</td><td colspan="2">${esc(r.raw.reason || "")}</td></tr>`);
    return `<table class="read"><caption>${esc(r.kind.replace(/_/g, " "))}</caption>${rows.join("")}</table>`;
  }).join("");
  const graph = d.incidents.filter((r) => r.evidence?.counts).map((r) => `<div class="evg"><div class="evg-h">${esc(r.kind.replace(/_/g, " "))}
      <span class="faint">${esc(r.evidence.required_path)}</span></div>
      <div class="path">${r.evidence.example.map(node).join("")}</div>
      <div class="chips evg-n">${Object.entries(r.evidence.counts).map(([k, v]) => `<span class="chip"><b>${v}</b> ${esc(k)}</span>`).join("")}</div>
      <ul class="evg-f">${r.evidence.fact_check.map((c) => `<li class="${c.ok ? "ok" : "no"}">${c.ok ? ICON.ok : ICON.no}<span>${esc(c.claim)}</span></li>`).join("")}</ul></div>`).join("");
  const denied = d.loaners_denied.length ? `<div class="sect"><div class="callout"><b>${d.loaners_denied.length} eligible customers waited for a loaner</b><ul>${d.loaners_denied
    .map((x) => `<li><span class="mono">${esc(x.customer_order_id)}</span> at ${esc(x.dealer_id)}: priority ${esc(x.priority)}, pool of ${x.pool}</li>`).join("")}</ul></div></div>` : "";
  return `<div class="sect"><div class="label">How the message was read<span>${esc(d.model || d.read_by)}</span></div>${reads}</div>
    ${graph ? `<div class="sect"><div class="label">Graph evidence<span>checked against the knowledge graph</span></div>${graph}</div>` : ""}${denied}
    <div class="sect"><div class="label">Trace any record</div><form class="search" id="traceForm"><input id="traceInput" placeholder="C1633, CO-02638, PO-0437, D25"><button class="btn">Trace</button></form>
    <div id="traceOut" style="margin-top:12px"></div></div>`;
}

async function trace(id) {
  side = "explain"; sidePane();
  $("#traceInput").value = id.split(":").pop();
  $("#traceOut").innerHTML = `<p class="placeholder">Tracing</p>`;
  try {
    const w = await api(`/api/why/${encodeURIComponent(id)}`);
    $("#traceOut").innerHTML = `<div class="label" style="margin-bottom:8px">${esc(w.label)} &middot; ${w.stories.length} actions</div>` + (w.stories.length ? w.stories.map((s) =>
      `<div class="story"><h4>${TOOL[s.action] || esc(s.action)} <span class="faint mono">${esc(s.event)}</span></h4><p>${esc(s.reason)}</p>
      <div class="path">${s.path.map(node).join("")}</div></div>`).join("") : `<p class="placeholder">No action touched this record.</p>`) +
      `<a class="btn" style="margin-top:8px" href="#/network/${encodeURIComponent(w.node)}">Open in Supply network</a>`;
  } catch (err) { $("#traceOut").innerHTML = `<p class="placeholder error">${esc(err.message)}</p>`; }
}

function sidePane() {
  $$("#sideTabs .tab").forEach((t) => t.classList.toggle("on", t.dataset.s === side));
  if (!detail) return;
  $("#sideBody").innerHTML = side === "actions" ? actions(detail) : explain(detail);
  if (side === "explain") $("#traceForm").onsubmit = (e) => { e.preventDefault(); const v = $("#traceInput").value.trim(); if (v) trace(v); };
}

function stage() {
  $$("#viewTabs .tab").forEach((t) => t.classList.toggle("on", t.dataset.v === view));
  $$(".stage-body > section").forEach((s) => s.classList.toggle("on", s.id === `v-${view}`));
  flow?.destroy(); line?.destroy(); flow = line = null;
  const d = detail, quiet = d.status === "review" || d.status === "ignored";
  $("#emptyBox").style.display = quiet ? "grid" : "none";
  $("#emptyBox").innerHTML = quiet ? `<div><p class="kicker">${d.status === "review" ? "Needs review" : "Noise ignored"}</p><h3>${d.status === "review"
    ? "Handed to a human" : "Nothing to contain"}</h3><p style="max-width:46ch">${esc(d.incidents[0]?.raw?.reason || "")}</p></div>` : "";
  if (quiet) { map?.reset(); return; }
  if (view === "map") map?.ripple(d.geo);
  if (view === "graph") flow = drawFlow($("#v-graph"), d, (n) => (n.members ? trace(n.members[0].id) : trace(n.id)));
  if (view === "timeline") line = drawTimeline($("#v-timeline"), d.schedule, (id) => focusAction(id.split(":").pop()));
}

async function select(id) {
  current = id;
  history.replaceState(null, "", `#/incidents/${encodeURIComponent(id)}`);
  $$(".qrow").forEach((el) => el.classList.toggle("on", el.dataset.id === id));
  $(".qrow.on")?.scrollIntoView({ block: "nearest" });
  const d = await eventDetail(id);
  if (current !== id) return;
  detail = d;
  incident(d);
  sidePane();
  stage();
}

export default {
  async enter(el, id) {
    el.innerHTML = `<section class="tower">
      <aside class="pane"><div class="pane-head"><span class="code">01</span><h2>Incident queue</h2><span class="right label" id="queueCount"></span></div>
        <div class="counts" id="counts"></div><div class="scroll"><ol class="queue" id="queue"></ol></div></aside>
      <div class="center">
        <article class="pane incident" id="incident"><p class="placeholder">Loading</p></article>
        <section class="pane stage"><div class="pane-head"><span class="code">02</span><div class="tabs" id="viewTabs">${Object.entries(VIEWS)
          .map(([k, v]) => `<button class="tab" data-v="${k}">${v}</button>`).join("")}</div><div class="right"><button class="btn" id="replay">Replay</button></div></div>
          <div class="stage-body grid-bg"><section id="v-map"></section><section id="v-graph"></section><section id="v-timeline"></section><div class="empty" id="emptyBox" style="display:none"></div></div>
          <div class="footbar" id="footbar"></div></section>
      </div>
      <aside class="pane"><div class="pane-head"><span class="code">03</span><div class="tabs" id="sideTabs">${Object.entries(SIDES)
        .map(([k, v]) => `<button class="tab" data-s="${k}">${v}</button>`).join("")}</div></div><div class="scroll pane-body" id="sideBody"></div></aside>
    </section>`;
    $$("#viewTabs .tab").forEach((t) => t.onclick = () => { view = t.dataset.v; detail && stage(); });
    $$("#sideTabs .tab").forEach((t) => t.onclick = () => { side = t.dataset.s; sidePane(); });
    $("#replay").onclick = () => detail && (view === "map" ? map?.ripple(detail.geo) : view === "graph" ? flow?.replay() : line?.replay());
    events = (await overview()).events;
    if (["all", "review", "resolved", "ignored"].includes(id)) { filter = id; id = events.find((e) => match(e, filter))?.event_id; }
    current = id && events.some((e) => e.event_id === id) ? id : current && events.some((e) => e.event_id === current) ? current : events[0].event_id;
    queue();
    $("#v-map").classList.add("on");
    map = await createMap($("#v-map"));
    await select(current);
  },
  async refresh(id) {
    forget();
    events = (await overview()).events;
    filter = "all";
    current = id;
    queue();
    await select(id);
  },
  leave() { map?.destroy(); flow?.destroy(); line?.destroy(); map = flow = line = detail = null; },
};
