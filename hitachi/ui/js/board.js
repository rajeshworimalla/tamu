import { $, $$, IC, api, esc, time, title } from "./core.js";
import { createMap } from "./usmap.js";

let map, onEsc;
const KIND = { outage: ["var(--crit)", "Plant down"], delay: ["var(--review)", "Part missing"], quality: ["#C98BD6", "Builds on quality hold"] };
const DAY = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const go = (id) => { location.hash = `#/incidents/${encodeURIComponent(id)}`; };

function numbers(t, events) {
  const n = (s) => events.filter((e) => e.status === s).length;
  const tiles = [["Messages", events.length, `${n("resolved")} acted, ${n("review")} escalated, ${n("ignored")} ignored`],
    ["Builds moved", t.builds_moved, `${t.transferred} to another plant`], ["Order delays sent", t.orders_delayed, `in ${t.dealer_notices} dealer notices`],
    ["Loaner cars", t.loaners, "Platinum and Gold first"], ["Lots held", t.lots_held, "defective parts quarantined"],
    ["Cars stopped", t.vehicles_stopped, "unsold, at dealers"], ["Owners contacted", t.owners_contacted, "sold cars with bad parts"]];
  $("#nums").innerHTML = tiles.map(([l, v, s]) => `<a href="#/evidence"><span class="label">${l}</span><b>${v.toLocaleString()}</b><small>${s}</small></a>`).join("");
}

function calendar(c) {
  const box = $("#cal"), labelW = 132, headH = 40, laneH = 22, pad = 6;
  const colW = Math.max(26, Math.floor((box.clientWidth - labelW - 24) / c.days.length));
  const x = (i) => labelW + (i - c.days[0].idx) * colW;
  const lanes = {};
  c.blocks.sort((a, b) => a.from - b.from).forEach((b) => {
    const used = (lanes[b.plant] ||= []);
    let k = used.findIndex((end) => end < b.from);
    if (k < 0) { k = used.length; used.push(0); }
    used[k] = b.to; b.lane = k;
  });
  let y = headH;
  const rowY = {};
  c.plants.forEach((p) => { rowY[p.id] = y; y += Math.max(1, (lanes[p.id] || []).length) * laneH + pad * 2 + 4; });
  const today = c.days.find((d) => d.idx === 0);
  let html = c.days.map((d) => {
    const dt = new Date(`${d.date}T12:00:00`), mon = dt.getDay() === 1;
    return `<div class="cal-day ${d.idx === 0 ? "today" : ""}" style="left:${x(d.idx)}px;width:${colW}px">${mon ? `<b>${dt.toLocaleString("en", { month: "short" }).toUpperCase()} ${dt.getDate()}</b>` : ""}<span>${DAY[dt.getDay()][0]}</span></div>`;
  }).join("");
  html += `<div class="cal-past" style="left:${labelW}px;width:${x(0) - labelW}px;height:${y}px"><span>ALREADY BUILT</span></div>`;
  html += `<div class="cal-now" style="left:${x(today.idx)}px;height:${y}px"><span>TODAY</span></div>`;
  c.plants.forEach((p) => {
    html += `<div class="cal-row" style="top:${rowY[p.id]}px;width:${labelW - 10}px">${esc(p.city.toUpperCase())}<small>${esc(p.id)}</small></div>`;
    html += `<div class="cal-line" style="top:${rowY[p.id] - 2}px;left:${labelW}px;width:${c.days.length * colW}px"></div>`;
  });
  html += c.blocks.map((b) => `<button class="cal-block ${b.kind}" data-ev="${esc(b.event)}" title="${esc(`${b.event}: ${b.label}`)}"
    style="left:${x(b.from) + 1}px;width:${(b.to - b.from + 1) * colW - 2}px;top:${rowY[b.plant] + pad + b.lane * laneH}px;height:${laneH - 4}px">
    <b>${esc(b.event)}</b> ${esc(b.label)}</button>`).join("");
  box.innerHTML = `<div class="cal" style="height:${y + 4}px">${html}</div>`;
  $$(".cal-block", box).forEach((b) => b.onclick = () => go(b.dataset.ev));
}

function morning(events) {
  const box = $("#morning"), W = box.clientWidth, H = box.clientHeight, l = 92, r = 24, t = 30;
  const lanes = [["resolved", "Acted on"], ["review", "Escalated"], ["ignored", "Ignored"]];
  const mins = (e) => { const [h, m] = time(e.received_at).split(":").map(Number); return h * 60 + m; };
  const lo = 7 * 60, hi = 11 * 60 + 30, X = (m) => l + ((m - lo) / (hi - lo)) * (W - l - r);
  const laneY = (s) => t + 10 + lanes.findIndex(([k]) => k === s) * ((H - t - 30) / 3) + (H - t - 30) / 6;
  let svg = "";
  for (let h = 7; h <= 11; h++) svg += `<line x1="${X(h * 60)}" x2="${X(h * 60)}" y1="${t - 6}" y2="${H - 16}" class="grid-line"/><text x="${X(h * 60)}" y="${t - 12}" class="axis" text-anchor="middle">${String(h).padStart(2, "0")}:00</text>`;
  lanes.forEach(([k, name]) => { svg += `<text x="12" y="${laneY(k) + 4}" class="axis">${name.toUpperCase()}</text><line x1="${l}" x2="${W - r}" y1="${laneY(k)}" y2="${laneY(k)}" class="lane"/>`; });
  events.filter((e) => !e.event_id.startsWith("LIVE")).forEach((e) => {
    const lane = ["blocked", "partial", "failed"].includes(e.status) ? "review" : e.status, rad = 5 + Math.min(16, Math.sqrt(e.actions) * 1.3);
    svg += `<g class="ev-dot st-${e.status}" data-ev="${esc(e.event_id)}" transform="translate(${X(mins(e))},${laneY(lane)})"><title>${esc(`${e.event_id} ${time(e.received_at)}: ${title(e.classification)}. ${e.summary}`)}</title>
      <circle r="${rad}"/><text y="${rad + 13}" text-anchor="middle">${esc(e.event_id)}</text></g>`;
  });
  box.innerHTML = `<svg width="${W}" height="${H}">${svg}</svg>`;
  $$(".ev-dot", box).forEach((g) => g.onclick = () => go(g.dataset.ev));
}

export default {
  async enter(el) {
    el.innerHTML = `<section class="board">
      <div class="pane"><div class="pane-head"><span class="code">00</span><h2>Overview &middot; Mon Mar 8</h2></div><div class="nums" id="nums"></div></div>
      <div class="board-mid">
        <div class="pane"><div class="pane-head"><span class="code">01</span><h2>Network impact</h2><span class="right legend"><span><i class="dot" style="background:var(--crit)"></i>Disrupted plant</span>
          <span><i class="dot" style="background:var(--review)"></i>Supplier</span><span><i class="dot" style="background:var(--accent)"></i>Dealer reached, sized by impact</span></span></div>
          <div class="stage-body grid-bg" style="flex:1"><div id="boardMap" style="position:absolute;inset:0"></div></div></div>
        <div class="pane"><div class="pane-head"><span class="code">02</span><h2>Event timeline</h2><span class="right label">Size: actions</span></div><div id="morning" style="flex:1;min-height:0"></div></div>
      </div>
      <div class="pane"><div class="pane-head"><span class="code">03</span><h2>Disruption calendar</h2><span class="right legend">${Object.values(KIND).map(([c, n]) => `<span><i class="sw" style="background:${c}"></i>${n}</span>`).join("")}</span></div>
        <div id="cal" style="padding:12px 12px 8px;overflow-x:auto"></div></div>
    </section>`;
    const b = await api("/api/board");
    numbers(b.totals, b.events);
    calendar(b.calendar);
    morning(b.events);
    const onPlant = (plant) => {
      const hit = b.calendar.blocks.find((x) => x.plant === plant && x.kind !== "quality") || b.calendar.blocks.find((x) => x.plant === plant);
      if (hit) go(hit.event);
    };
    const redraw = {
      map: async () => { map?.destroy(); map = await createMap($("#boardMap")); map.overview(b.geo, onPlant); },
      morning: () => morning(b.events), cal: () => calendar(b.calendar),
    };
    const toggle = (pane, key, force) => {
      const on = force ?? !pane.classList.contains("max");
      pane.classList.toggle("max", on);
      pane.querySelector(".expand").innerHTML = on ? IC.collapse : IC.expand;
      pane.querySelector(".expand").title = on ? "Back to board (Esc)" : "Expand to full screen";
      requestAnimationFrame(() => redraw[key]());
    };
    $$(".board .pane").forEach((pane, i) => {
      const key = [null, "map", "morning", "cal"][i];
      if (!key) return;
      const btn = document.createElement("button");
      btn.className = "btn expand";
      btn.title = "Expand to full screen";
      btn.innerHTML = IC.expand;
      btn.onclick = () => toggle(pane, key);
      pane.querySelector(".pane-head").append(btn);
      pane.dataset.key = key;
    });
    onEsc = (e) => { const p = $(".pane.max"); if (e.key === "Escape" && p) toggle(p, p.dataset.key, false); };
    window.addEventListener("keydown", onEsc);
    await redraw.map();
  },
  leave() { map?.destroy(); map = null; window.removeEventListener("keydown", onEsc); },
};
