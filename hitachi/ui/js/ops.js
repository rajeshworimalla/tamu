import { $, $$, IC, esc, eventDetail, overview, pill, title } from "./core.js";
import { createMap } from "./usmap.js";

let map, current, view = "network", events = [], resizer;
const ICON = { "Supplier Delay": IC.truck, "Plant Outage": IC.factory, "Quality Hold": IC.shield, "Unconfirmed Report": IC.alert };
const NODES = [["supplier", "Supplier", IC.truck, "left"], ["parts", "Parts", IC.cog, "left"], ["models", "Models", IC.car, "left"],
  ["builds", "Builds", IC.calendar, "right"], ["dealers", "Dealers", IC.store, "right"], ["customers", "Customers", IC.users, "right"]];

function kpis(o) {
  const t = o.totals, tools = t.tools || {}, review = o.events.filter((e) => NEEDS_REVIEW.includes(e.status)).length;
  const cards = [["#/incidents/all", IC.msg, t.events, "", "Events"],
    ["#/incidents/review", IC.alert, review, "", "Needs review", review ? "warn" : ""],
    ["#/evidence/agent=Supply Chain Planner", IC.calendar, (tools["mes.reschedule"] || 0) + (tools["mes.transfer"] || 0), "", "Builds moved"],
    ["#/evidence/tool=crm.notify_customer", IC.users, tools["crm.notify_customer"] || 0, "", "Customers notified"],
    ["#/evidence/tool=crm.assign_loaner", IC.car, tools["crm.assign_loaner"] || 0, "", "Loaners assigned"]];
  $("#kpis").innerHTML = cards.map(([href, ic, v, suf, l, cls = ""]) => `<a class="kpi pane" href="${href}"><span class="tile ${cls}">${ic}</span>
    <span><b>${v}<small>${suf}</small></b><span>${l}</span></span></a>`).join("");
}

const NEEDS_REVIEW = ["review", "blocked", "partial", "failed"];
const GROUPS = [["Needs review", NEEDS_REVIEW], ["Ready to send", ["verified"]], ["Resolved", ["resolved"]]];

function list() {
  const active = events.filter((e) => e.status !== "ignored"), quiet = events.length - active.length;
  const row = (e) => `<button class="inc ${e.event_id === current ? "on" : ""}" data-id="${esc(e.event_id)}">
    <span class="tile ${NEEDS_REVIEW.includes(e.status) ? "warn" : ""}">${ICON[e.classification] || (e.classification.startsWith("Compound") ? IC.layers : IC.alert)}</span>
    <span class="inc-text"><b>${esc(e.event_id)} &middot; ${esc(title(e.classification))}</b><span>${esc(e.tagline)}</span></span>${pill(e.status)}</button>`;
  $("#incCount").textContent = `Incidents (${active.length})`;
  $("#incList").innerHTML = GROUPS.map(([name, sts]) => {
    const xs = active.filter((e) => sts.includes(e.status));
    return xs.length ? `<p class="inc-group">${name} &middot; ${xs.length}</p>${xs.map(row).join("")}` : "";
  }).join("") + (quiet ? `<a class="inc-quiet" href="#/incidents">${quiet} messages ignored as noise. See them in Incidents.</a>` : "");
  $$(".inc").forEach((b) => b.onclick = () => select(b.dataset.id));
}

function hub(d) {
  const box = $("#hub"), h = d.hub;
  if (!h) {
    box.innerHTML = `<div class="hub-empty"><div class="hub-core quiet">${IC.alert}<b>No ripple</b></div>
      <p>${esc(d.status === "review" ? "Unconfirmed or incomplete. Sent for review, no records changed." : "Not related to operations. No records changed.")}</p></div>`;
    return;
  }
  const W = box.clientWidth, H = box.clientHeight, cx = W / 2, cy = H / 2 - 6, R = Math.min(78, H / 4.2);
  const rows = [cy - H * 0.29, cy, cy + H * 0.29], gap = Math.min(W * 0.36, 300);
  const pos = {}, NAMES = h.names || {};
  NODES.forEach(([k, , , side], i) => { pos[k] = { x: side === "left" ? cx - gap : cx + gap, y: rows[i % 3], side }; });
  const curves = NODES.map(([k]) => {
    const p = pos[k], sx = p.side === "left" ? p.x + 74 : p.x - 74, ex = p.side === "left" ? cx - R : cx + R, mid = (sx + ex) / 2;
    return `<path d="M${sx},${p.y} C${mid},${p.y} ${mid},${cy} ${ex},${cy}" class="${h.counts[k] ? "" : "off"}"/><circle cx="${sx}" cy="${p.y}" r="3.5" class="${h.counts[k] ? "" : "off"}"/>`;
  }).join("");
  const place = h.center.map((c) => c.city).join(" + ");
  box.innerHTML = `<div class="hub-floor"></div><svg class="hub-lines" width="${W}" height="${H}">${curves}</svg>
    <a class="hub-core" href="#/incidents/${encodeURIComponent(d.event_id)}" style="left:${cx}px;top:${cy}px;width:${R * 2}px;height:${R * 2}px">${IC.factory}
      <b>${esc(place.toUpperCase())}</b><span>${h.center.length > 1 ? "Plants" : "Plant"}</span></a>` +
    NODES.map(([k, name, ic]) => {
      const p = pos[k], n = h.counts[k], sample = (NAMES[k] || []).slice(0, 2).join(", ");
      return `<a class="hub-node ${n ? "" : "off"}" href="#/incidents/${encodeURIComponent(d.event_id)}" title="${esc(sample || name)}"
        style="left:${p.x}px;top:${p.y}px">${ic}<span><b>${name}</b><em>${n ? n.toLocaleString() : "none"}</em>${sample ? `<small>${esc(sample)}</small>` : ""}</span></a>`;
    }).join("");
}

function stage(d) {
  $$("#hubTabs .tab").forEach((t) => t.classList.toggle("on", t.dataset.v === view));
  $("#hub").style.display = view === "network" ? "" : "none";
  $("#opsMap").style.display = view === "map" ? "" : "none";
  if (view === "network") hub(d);
  else if (d.hub) map?.ripple(d.geo);
  else map?.reset();
}

async function select(id) {
  current = id;
  $$(".inc").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
  $(".inc.on")?.scrollIntoView({ block: "nearest" });
  const d = await eventDetail(id);
  if (current !== id) return;
  $("#rippleSub").textContent = d.hub ? `${title(d.classification)} around ${d.hub.center.map((c) => c.city).join(" and ")}. ${d.summary}` : d.summary;
  $("#openInc").href = `#/incidents/${encodeURIComponent(id)}`;
  stage(d);
}

export default {
  async enter(el) {
    el.innerHTML = `<section class="ops">
      <div class="kpis" id="kpis"></div>
      <div class="ops-mid">
        <div class="pane"><div class="pane-head" style="min-height:76px"><div><h2 style="font-size:20px">Impact analysis</h2><p class="faint" id="rippleSub" style="margin-top:2px"></p></div>
          <div class="right"><div class="tabs" id="hubTabs"><button class="tab" data-v="network">Network</button><button class="tab" data-v="map">Map</button></div>
          <a class="btn" id="openInc">Open incident</a></div></div>
          <div class="stage-body" style="flex:1"><div id="hub" class="hub"></div><div id="opsMap" style="position:absolute;inset:0"></div></div></div>
        <div class="pane"><div class="pane-head"><h2 id="incCount">Incidents</h2><a class="right link-ok" href="#/incidents">View all</a></div>
          <div class="scroll" id="incList" style="padding:10px"></div></div>
      </div>
    </section>`;
    const o = await overview();
    events = o.events;
    kpis(o);
    current = current && events.some((e) => e.event_id === current) ? current
      : (events.find((e) => e.event_id === "E-10") || events.find((e) => e.status === "resolved") || events[0]).event_id;
    list();
    $$("#hubTabs .tab").forEach((t) => t.onclick = () => { view = t.dataset.v; select(current); });
    map = await createMap($("#opsMap"));
    await select(current);
    resizer = () => { clearTimeout(resizer.t); resizer.t = setTimeout(() => view === "network" && select(current), 150); };
    window.addEventListener("resize", resizer);
  },
  leave() { map?.destroy(); map = null; window.removeEventListener("resize", resizer); },
};
