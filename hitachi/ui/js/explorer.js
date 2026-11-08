import { $, $$, TOOL, api, esc } from "./core.js";

const COLOR = { Plant: "#A5D6B1", Model: "#8FB8C9", Part: "#C8B38A", Supplier: "#E3B55B", Shipment: "#E3B55B", Lot: "#D98C6E",
  ProductionOrder: "#7FA894", CustomerOrder: "#93B5A4", Dealer: "#B9CDBF", Customer: "#F3F3E9", Vehicle: "#6C8478" };
const STARTS = ["Shipment:SH-0248", "Lot:LOT-0130", "Plant:P_AL", "Customer:C1633", "Dealer:D25", "Part:CAM-360"];
let cy, timer;
const REL = {
  out: { ships: "shipment it sends", made: "lot it made", carries: "part on board", delivers_to: "headed to", batch_of: "part in this lot", used_at: "used at",
    installed_in: "installed in", builds: "model built here", contains: "part it uses", scheduled_at: "built at", of_model: "model", promised_to: "customer order",
    placed_at: "dealer", for: "customer", produced: "car built", stocked_at: "in stock at", sold_by: "sold by", owned_by: "owner" },
  in: { ships: "supplier", made: "made by", carries: "shipment carrying it", delivers_to: "shipment arriving", batch_of: "lot of this part", used_at: "lot used here",
    installed_in: "lot installed", builds: "plant that builds it", contains: "model that uses it", scheduled_at: "build here", of_model: "build of this model",
    promised_to: "build behind it", placed_at: "customer order", for: "customer order", produced: "build that made it", stocked_at: "car in stock",
    sold_by: "car sold here", owned_by: "car owned" },
};

const name = (t) => t.replace(/([a-z])([A-Z])/g, "$1 $2");

async function results(q) {
  const box = $("#results");
  if (q.trim().length < 2) {
    box.innerHTML = `<div class="pane-body"><div class="label" style="margin-bottom:8px">Start from</div><div class="chips">${STARTS
      .map((s) => `<a class="chip" href="#/network/${encodeURIComponent(s)}">${esc(s.split(":")[1])}</a>`).join("")}</div>
      <p class="hint" style="margin-top:12px">Search 16,989 records: customers, production orders, vehicles, lots, shipments, dealers.</p></div>`;
    return;
  }
  const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
  box.innerHTML = r.map((x) => `<a class="result" href="#/network/${encodeURIComponent(x.id)}"><span>${esc(x.label)}</span><span class="label">${esc(name(x.type))}</span></a>`).join("")
    || `<p class="placeholder">No record matches</p>`;
}

function draw(n) {
  cy?.destroy();
  const cap = (x) => (REL[x.dir][x.rel] || x.rel.replace(/_/g, " "));
  const els = [{ data: { id: n.id, text: n.label, type: n.type, center: 1, acted: n.stories.length ? 1 : 0 } }]
    .concat(n.neighbors.map((x) => ({ data: { id: x.id, text: `${x.label}\n${cap(x)}`, type: x.type, center: 0 } })))
    .concat(n.neighbors.map((x) => ({ data: { id: `${x.id}~${x.rel}`, source: n.id, target: x.id } })));
  cy = cytoscape({
    container: $("#graph"), elements: els, wheelSensitivity: 0.25, minZoom: 0.3, maxZoom: 3,
    layout: { name: "concentric", concentric: (x) => (x.data("center") ? 2 : 1), levelWidth: () => 1, minNodeSpacing: 58, padding: 50, animate: true, animationDuration: 350 },
    style: [
      { selector: "node", style: { width: 20, height: 20, "background-color": (x) => COLOR[x.data("type")] || "#6C8478", label: "data(text)", color: "#D6EEDC",
        "font-family": "Inter, sans-serif", "font-size": 11.5, "text-valign": "bottom", "text-margin-y": 7, "text-wrap": "wrap", "text-max-width": 150,
        "line-height": 1.35, "text-outline-color": "#0E2119", "text-outline-width": 3 } },
      { selector: "node[center = 1]", style: { width: 44, height: 44, "border-width": 3, "border-color": "#F3F3E9", "font-size": 14, "font-weight": 700 } },
      { selector: "node[acted = 1]", style: { "border-color": "#7EE2A8", "border-width": 4 } },
      { selector: "edge", style: { width: 1.2, "line-color": "#2B5040", "curve-style": "straight", opacity: 0.8 } },
      { selector: "node:active, node:selected", style: { "overlay-opacity": 0 } },
    ],
  });
  $("#gctrl").innerHTML = "";
  [["+", "Zoom in", () => cy.animate({ zoom: cy.zoom() * 1.4, center: { eles: cy.$(`[center = 1]`) } }, { duration: 200 })],
    ["−", "Zoom out", () => cy.animate({ zoom: cy.zoom() / 1.4 }, { duration: 200 })],
    ["○", "Fit", () => cy.animate({ fit: { padding: 50 } }, { duration: 300 })]].forEach(([t, title, fn]) => {
    const b = document.createElement("button");
    Object.assign(b, { textContent: t, title, onclick: fn });
    b.setAttribute("aria-label", title);
    $("#gctrl").append(b);
  });
  cy.on("tap", "node", (e) => { if (!e.target.data("center")) location.hash = `#/network/${encodeURIComponent(e.target.id())}`; });
  $("#legend").innerHTML = [...new Set([n.type, ...n.neighbors.map((x) => x.type)])]
    .map((t) => `<span><i class="dot" style="background:${COLOR[t] || "#6C8478"}"></i>${esc(name(t).toUpperCase())}</span>`).join("") +
    (n.more.length ? `<span style="margin-left:auto">${n.more.reduce((s, m) => s + m.hidden, 0)} more links not drawn</span>` : "");
}

function record(n) {
  const info = Object.entries(n.info).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
  $("#record").innerHTML = `<div class="sect"><span class="label">${esc(name(n.type))}</span><h2 class="serif" style="font-size:30px;line-height:1.1;margin-top:4px">${esc(n.label)}</h2>
      <p class="mono faint" style="margin-top:4px">${esc(n.id)}</p></div>
    ${info ? `<div class="sect"><div class="label">Attributes</div><dl class="kv">${info}</dl></div>` : ""}
    <div class="sect"><div class="label">Actions on this record<span>${n.stories.length}</span></div>${n.stories.length ? n.stories.map((s) =>
      `<div class="story"><h4>${TOOL[s.action] || esc(s.action)} <a class="mono faint" href="#/incidents/${encodeURIComponent(s.event)}">${esc(s.event)}</a></h4>
      <p>${esc(s.reason)}</p><p class="faint mono">${esc(s.agent)} &middot; rule ${esc(s.rule)}</p></div>`).join("")
      : `<p class="placeholder">No action touched this record</p>`}</div>
    ${n.more.length ? `<div class="sect"><div class="label">Not drawn</div>${n.more.map((m) => `<div class="row-mini mono faint">${esc(m.rel.replace(/_/g, " "))} ${esc(name(m.type))}: ${m.hidden} more</div>`).join("")}</div>` : ""}`;
}

export default {
  async enter(el, id) {
    el.innerHTML = `<section class="explorer">
      <aside class="pane"><div class="pane-head"><span class="code">01</span><h2>Find a record</h2></div>
        <div class="pane-body" style="border-bottom:1px solid var(--line)"><form class="search" id="find"><input id="q" placeholder="Customer, production order, vehicle or lot" autocomplete="off"></form></div>
        <div class="scroll" id="results"></div></aside>
      <section class="pane"><div class="pane-head"><span class="code">02</span><h2>Relationships</h2><span class="right label">Click to expand &middot; scroll to zoom</span></div>
        <div class="stage-body grid-bg" style="flex:1"><div id="graph" style="position:absolute;inset:0"></div><div class="map-ctrl" id="gctrl"></div></div><div class="footbar legend" id="legend" style="margin:0"></div></section>
      <aside class="pane"><div class="pane-head"><span class="code">03</span><h2>Record</h2></div><div class="scroll pane-body" id="record"></div></aside>
    </section>`;
    $("#q").oninput = (e) => { clearTimeout(timer); timer = setTimeout(() => results(e.target.value), 180); };
    $("#find").onsubmit = (e) => { e.preventDefault(); const first = $("#results .result"); if (first) location.hash = first.getAttribute("href"); };
    results("");
    const target = id || STARTS[0];
    try {
      const n = await api(`/api/node/${encodeURIComponent(target)}`);
      draw(n); record(n);
    } catch (err) { $("#record").innerHTML = `<p class="placeholder error">${esc(err.message)}</p>`; }
    $("#q").focus();
  },
  leave() { cy?.destroy(); cy = null; clearTimeout(timer); },
};
