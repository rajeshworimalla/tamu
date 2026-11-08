import { $$, esc } from "./core.js";

const DAY = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

export function drawTimeline(el, s, onOrder) {
  let timer;
  if (!s) {
    el.innerHTML = `<div class="empty"><div><h3>No schedule change</h3><p>This incident does not move any build.</p></div></div>`;
    return { destroy() {} };
  }
  el.innerHTML = `<div class="timeline">
    <div class="tl-head"><div><span class="label">Production schedule</span>
      <div class="mono" style="margin-top:4px">${s.moved} builds moved &middot; ${s.transferred} transferred to another plant &middot; average shift +${s.avg_shift} working days</div></div>
      <div class="chips" id="tlMode"><button class="chip on" data-m="before">Before</button><button class="chip" data-m="after">After recovery</button></div></div>
    <div class="tl-grid"></div>
    <div class="tl-legend"><span><i class="sw" style="background:var(--surface);border:1px solid var(--line-2)"></i>Unaffected build</span>
      <span><i class="sw" style="background:var(--crit)"></i>Affected, original slot</span><span><i class="sw" style="background:var(--accent)"></i>Rescheduled, same plant</span>
      <span><i class="sw" style="background:var(--review)"></i>Transferred</span><span><i class="sw" style="background:repeating-linear-gradient(135deg,rgba(229,115,90,.5) 0 3px,transparent 3px 6px)"></i>Blocked by the disruption</span></div></div>`;
  const grid = el.querySelector(".tl-grid"), labelW = 150, headH = 26, slotH = 21, pad = 5;
  const dayW = Math.max(74, Math.floor((el.clientWidth - 40 - labelW) / s.days.length));
  const rowH = Math.max(...s.plants.map((p) => p.slots)) * slotH + pad * 2;
  const col = Object.fromEntries(s.days.map((d, i) => [d.idx, labelW + i * dayW]));
  const row = Object.fromEntries(s.plants.map((p, i) => [p.id, headH + i * (rowH + 8)]));
  grid.style.height = `${headH + s.plants.length * (rowH + 8)}px`;
  grid.style.width = `${labelW + s.days.length * dayW}px`;
  const blocked = (p, idx) => s.blocked.find((b) => b.plant === p && b.from <= idx && idx <= b.to);
  let html = s.days.map((d) => {
    const dt = new Date(`${d.date}T12:00:00`);
    return `<div class="tl-day" style="left:${col[d.idx]}px;width:${dayW}px">${DAY[dt.getDay()]} ${dt.getDate()}</div>`;
  }).join("");
  s.plants.forEach((p) => {
    const why = s.blocked.filter((b) => b.plant === p.id).map((b) => (b.part ? `no ${b.part}` : "plant down")).join(", ");
    html += `<div class="tl-row" style="top:${row[p.id] + 6}px;width:${labelW - 12}px">${esc(p.city.toUpperCase())}
      <div class="faint" style="font-weight:500;letter-spacing:.04em;margin-top:2px">${esc(p.id)} &middot; ${p.slots} slots/day</div>
      ${why ? `<div style="color:var(--crit);font-weight:500;margin-top:2px">${esc(why)}</div>` : ""}</div>`;
    s.days.forEach((d) => {
      html += `<div class="tl-cell ${blocked(p.id, d.idx) ? "blocked" : ""}" style="left:${col[d.idx] + 2}px;top:${row[p.id]}px;width:${dayW - 4}px;height:${rowH}px"></div>`;
    });
  });
  html += s.orders.map((o) => `<button class="tl-chip ${o.moved ? "moved" : ""} ${o.transfer ? "transfer" : ""}" data-po="${esc(o.po)}"
    title="${esc(`${o.po} ${o.model}${o.moved ? `, moved ${o.transfer ? "to another plant" : "later"}` : ""}`)}" style="width:${dayW - 12}px">${esc(o.po.replace("PO-", ""))} ${esc(o.model.slice(0, 3))}</button>`).join("");
  grid.innerHTML = html;

  const place = (mode) => {
    const cells = {};
    s.orders.forEach((o) => {
      const [p, i] = o[mode];
      (cells[`${p}|${i}`] ||= []).push(o);
    });
    Object.entries(cells).forEach(([key, list]) => {
      const [p, i] = key.split("|");
      list.sort((a, b) => a.moved - b.moved || a.po.localeCompare(b.po)).forEach((o, k) => {
        const chip = grid.querySelector(`[data-po="${o.po}"]`);
        if (col[i] === undefined || row[p] === undefined) { chip.style.display = "none"; return; }
        chip.style.display = "";
        chip.style.left = `${col[i] + 8}px`;
        chip.style.top = `${row[p] + pad + k * slotH}px`;
        chip.classList.toggle("after", mode === "after");
      });
    });
    $$("#tlMode .chip", el).forEach((b) => b.classList.toggle("on", b.dataset.m === mode));
  };
  place("before");
  $$("#tlMode .chip", el).forEach((b) => b.onclick = () => { clearTimeout(timer); place(b.dataset.m); });
  $$(".tl-chip", grid).forEach((c) => c.onclick = () => onOrder && onOrder(`ProductionOrder:${c.dataset.po}`));
  timer = setTimeout(() => place("after"), 1100);
  return { replay() { clearTimeout(timer); place("before"); timer = setTimeout(() => place("after"), 900); }, destroy() { clearTimeout(timer); el.innerHTML = ""; } };
}
