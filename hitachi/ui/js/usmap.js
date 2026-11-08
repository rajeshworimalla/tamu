import { api, esc } from "./core.js";

const SKIP = new Set(["02", "15", "60", "66", "69", "72", "78"]);
let base;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function loadBase() {
  base ||= Promise.all([fetch("/static/vendor/states-10m.json").then((r) => r.json()),
    fetch("/static/places.json").then((r) => r.json()), api("/api/places")]);
  return base;
}

function curve(a, b, bend = 0.18) {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1];
  return `M${a[0]},${a[1]} Q${mx - dy * bend},${my + dx * bend} ${b[0]},${b[1]}`;
}

export async function createMap(el) {
  const [topo, coords, meta] = await loadBase();
  const states = topojson.feature(topo, topo.objects.states);
  states.features = states.features.filter((f) => !SKIP.has(f.id));
  const W = el.clientWidth || 800, H = el.clientHeight || 500;
  const network = [...Object.values(meta.plants), ...Object.values(meta.dealers)].map((d) => coords[d.city]).filter(Boolean);
  const proj = d3.geoAlbers().rotate([90, 0]).fitExtent([[54, 46], [W - 54, H - 40]], { type: "MultiPoint", coordinates: network });
  const xy = (city) => (coords[city] ? proj(coords[city]) : null);
  const inside = (p) => p[0] >= 0 && p[0] <= W && p[1] >= 0 && p[1] <= H;
  const pin = (p) => [Math.max(14, Math.min(W - 14, p[0])), Math.max(14, Math.min(H - 14, p[1]))];
  el.classList.add("map");
  if (getComputedStyle(el).position === "static") el.style.position = "relative";
  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("preserveAspectRatio", "xMidYMid meet");
  const tip = d3.select(el).append("div").attr("class", "map-tip");
  const root = svg.append("g");
  const path = d3.geoPath(proj);
  root.append("g").selectAll("path").data(states.features).join("path").attr("class", "state").attr("d", path);
  const stateNames = root.append("g").selectAll("text").data(states.features.filter((f) => inside(path.centroid(f)))).join("text").attr("class", "state-name")
    .attr("x", (f) => path.centroid(f)[0]).attr("y", (f) => path.centroid(f)[1]).text((f) => f.properties.name.toUpperCase());
  const linkG = root.append("g"), dealerG = root.append("g"), supplierG = root.append("g"), plantG = root.append("g"), labelG = root.append("g");

  const seen = {};
  const dealers = Object.entries(meta.dealers).map(([id, d]) => {
    const p = xy(d.city) || [0, 0], n = (seen[d.city] = (seen[d.city] || 0) + 1) - 1;
    return { id, ...d, p: [p[0] + n * 7, p[1] + n * 5] };
  });
  const plants = Object.entries(meta.plants).map(([id, d]) => ({ id, ...d, p: xy(d.city) }));
  const byDealer = Object.fromEntries(dealers.map((d) => [d.id, d]));
  const byPlant = Object.fromEntries(plants.map((p) => [p.id, p]));
  let k = 1, run = 0, idleTimer;

  const show = (html, ev) => {
    const [x, y] = d3.pointer(ev, el);
    tip.html(html).style("left", `${Math.min(x + 14, el.clientWidth - 250)}px`).style("top", `${y + 14}px`).style("opacity", 1);
  };
  const hide = () => tip.style("opacity", 0);

  const dealerDots = dealerG.selectAll("circle").data(dealers).join("circle").attr("class", "dealer")
    .attr("cx", (d) => d.p[0]).attr("cy", (d) => d.p[1]).attr("r", 2.6)
    .on("mousemove", (ev, d) => show(`${esc(d.name)}<small>Dealer in ${esc(d.city)}${d.info ? ` &middot; ${esc(d.info)}` : ""}</small>`, ev)).on("mouseleave", hide);
  const halos = plantG.selectAll("circle.halo").data(plants).join("circle").attr("class", "halo")
    .attr("cx", (d) => d.p[0]).attr("cy", (d) => d.p[1]).attr("r", 6);
  const plantDots = plantG.selectAll("circle.plant").data(plants).join("circle").attr("class", "plant")
    .attr("cx", (d) => d.p[0]).attr("cy", (d) => d.p[1]).attr("r", 5.5)
    .on("mousemove", (ev, d) => show(`${esc(d.city.split(",")[0])} plant<small>${esc(d.id)}, builds cars daily</small>`, ev)).on("mouseleave", hide);
  const plantLabels = labelG.selectAll("text").data(plants).join("text").attr("class", "label small")
    .attr("x", (d) => d.p[0] + 9).attr("y", (d) => d.p[1] + 4).text((d) => d.city.split(",")[0]);

  function scaleMarks() {
    const s = Math.pow(k, 0.75);
    dealerDots.attr("r", (d) => (d.r || 2.6) / s);
    plantDots.attr("r", 5.5 / s).attr("stroke-width", 2 / s);
    halos.filter((d) => d.halo).attr("r", (d) => d.halo / s).style("stroke-width", `${1.2 / k}px`);
    labelG.selectAll("text").style("font-size", `${11 / k}px`).style("stroke-width", `${3 / k}px`);
    plantLabels.attr("x", (d) => d.p[0] + 9 / s).attr("y", (d) => d.p[1] + 4 / s);
    supplierG.selectAll("circle").attr("r", 5 / s).attr("stroke-width", 2 / s);
    stateNames.style("font-size", `${9.5 / k}px`);
    linkG.selectAll("path").style("stroke-width", function () { return `${(+this.dataset.w || 1.1) / k}px`; });
  }

  function declutter() {
    const placed = [], step = 13 / k;
    labelG.selectAll("text").each(function () {
      this.setAttribute("dy", 0);
      const b = this.getBBox();
      for (const off of [0, step, 2 * step, 3 * step, -step, -2 * step, 4 * step]) {
        const box = { x: b.x, y: b.y + off, w: b.width, h: b.height };
        if (!placed.some((p) => box.x < p.x + p.w && p.x < box.x + box.w && box.y < p.y + p.h && p.y < box.y + box.h)) {
          this.setAttribute("dy", off);
          placed.push(box);
          return;
        }
      }
      placed.push({ x: b.x, y: b.y, w: b.width, h: b.height });
    });
  }

  const zoom = d3.zoom().scaleExtent([1, 12]).translateExtent([[-W * 0.25, -H * 0.25], [W * 1.25, H * 1.25]])
    .on("zoom", (ev) => { root.attr("transform", ev.transform); k = ev.transform.k; scaleMarks(); declutter(); });
  svg.call(zoom).on("dblclick.zoom", null);
  const ctrl = d3.select(el).append("div").attr("class", "map-ctrl");
  [["+", "Zoom in", () => svg.transition().duration(300).call(zoom.scaleBy, 1.7)],
    ["−", "Zoom out", () => svg.transition().duration(300).call(zoom.scaleBy, 1 / 1.7)],
    ["○", "Reset view", () => svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity)]]
    .forEach(([t, title, fn]) => ctrl.append("button").attr("title", title).attr("aria-label", title).text(t).on("click", fn));

  function focus(points, ms = 900) {
    const pts = points.filter(Boolean);
    if (!pts.length) { svg.transition().duration(ms).call(zoom.transform, d3.zoomIdentity); return; }
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const kk = Math.max(1, Math.min(3.2, 0.78 / Math.max((x1 - x0 + 60) / W, (y1 - y0 + 60) / H)));
    const t = d3.zoomIdentity.translate(W / 2 - kk * (x0 + x1) / 2, H / 2 - kk * (y0 + y1) / 2).scale(kk);
    svg.transition().duration(ms).ease(d3.easeCubicInOut).call(zoom.transform, t);
  }

  function draw(path, cls, w, ms, delay = 0) {
    const p = linkG.append("path").attr("class", cls).attr("d", path).attr("data-w", w).style("stroke-width", `${w / k}px`);
    const len = p.node().getTotalLength();
    if (cls === "late") p.style("opacity", 0).transition().delay(delay).duration(ms).style("opacity", 1);
    else p.attr("stroke-dasharray", `${len} ${len}`).attr("stroke-dashoffset", len)
      .transition().delay(delay).duration(ms).ease(d3.easeCubicOut).attr("stroke-dashoffset", 0);
    return p;
  }

  function pulse(sel, cls) {
    sel.classed(cls, true).attr("r", 6).style("opacity", 0.9).transition().duration(1400).ease(d3.easeCubicOut)
      .attr("r", 34 / Math.pow(k, 0.75)).style("opacity", 0);
  }

  function reset() {
    run += 1;
    clearInterval(idleTimer);
    linkG.selectAll("*").interrupt().remove();
    supplierG.selectAll("*").remove();
    labelG.selectAll("text.extra").remove();
    dealers.forEach((d) => { d.r = 2.6; d.info = ""; });
    plants.forEach((p) => { p.halo = 0; });
    dealerDots.interrupt().classed("hit safe", false).attr("r", 2.6 / Math.pow(k, 0.75));
    plantDots.classed("hit", false);
    halos.interrupt().classed("hit", false).style("opacity", 0);
  }

  async function ripple(geo, opts = {}) {
    reset();
    const me = run, alive = () => me === run;
    const sources = geo.plants.map((id) => byPlant[id]).filter(Boolean);
    const sups = geo.suppliers.map((id) => meta.suppliers[id]).filter((s) => s && xy(s.city))
      .map((s) => ({ ...s, far: !inside(xy(s.city)), at: inside(xy(s.city)) ? xy(s.city) : pin(xy(s.city)) }));
    const hit = Object.entries(geo.dealers).map(([id, c]) => ({ d: byDealer[id], c })).filter((x) => x.d);
    const moves = geo.transfers.map((t) => [byPlant[t.from], byPlant[t.to]]).filter(([a, b]) => a && b);
    focus([...sources.map((s) => s.p), ...sups.filter((s) => !s.far).map((s) => s.at), ...hit.map((h) => h.d.p), ...moves.flat().map((p) => p.p)], opts.fast ? 500 : 900);
    await wait(opts.fast ? 500 : 900);
    if (!alive()) return;
    sups.forEach((s) => {
      const p = s.at, right = p[0] > W * 0.7;
      supplierG.append("circle").attr("class", "supplier").attr("cx", p[0]).attr("cy", p[1]).attr("r", 5 / Math.pow(k, 0.75))
        .on("mousemove", (ev) => show(`${esc(s.name)}<small>Supplier in ${esc(s.city)}</small>`, ev)).on("mouseleave", hide);
      labelG.append("text").attr("class", "label extra").attr("x", p[0] + (right ? -9 : 9) / k).attr("y", p[1] - 8 / k).style("font-size", `${11 / k}px`)
        .attr("text-anchor", right ? "end" : "start").style("stroke-width", `${3 / k}px`).text(s.far ? `${s.name} (${s.city})` : s.name);
      sources.forEach((t) => draw(curve(p, t.p, 0.12), "late", 2, 700));
    });
    declutter();
    if (sups.length) await wait(800);
    if (!alive()) return;
    plantDots.filter((d) => sources.includes(d)).classed("hit", true);
    for (let i = 0; i < 2; i++) { pulse(halos.filter((d) => sources.includes(d)), "hit"); await wait(450); }
    if (!alive()) return;
    hit.sort((a, b) => d3.geoDistance(coords[a.d.city], coords[sources[0]?.city]) - d3.geoDistance(coords[b.d.city], coords[sources[0]?.city]));
    const stagger = Math.min(45, 1400 / Math.max(hit.length, 1));
    hit.forEach(({ d, c }, i) => {
      const from = sources.reduce((best, s) => (!best || d3.geoDistance(coords[s.city], coords[d.city]) < d3.geoDistance(coords[best.city], coords[d.city]) ? s : best), null);
      if (from) draw(curve(from.p, d.p), "link", 1.1, 500, i * stagger);
      const n = (c.orders || 0) + (c.stopped || 0) + (c.owners || 0);
      d.r = 2.6 + Math.min(7, Math.sqrt(n) * 1.4);
      d.info = [c.orders && `${c.orders} orders delayed`, c.loaners && `${c.loaners} loaners`, c.stopped && `${c.stopped} cars on stop sale`,
        c.owners && `${c.owners} owners contacted`].filter(Boolean).join(", ");
      setTimeout(() => alive() && dealerDots.filter((x) => x === d).classed("hit", true).transition().duration(300)
        .attr("r", d.r / Math.pow(k, 0.75)), i * stagger + 450);
    });
    await wait(hit.length * stagger + 900);
    if (!alive()) return;
    moves.forEach(([a, b], i) => draw(curve(a.p, b.p, 0.3), "move", 2.2, 800, i * 200));
    if (moves.length) await wait(moves.length * 200 + 900);
    if (!alive()) return;
    dealerDots.filter((d) => hit.some((h) => h.d === d)).classed("hit", false).classed("safe", true);
    linkG.selectAll("path.link").classed("safe", true);
    plantDots.classed("hit", false);
  }

  function overview(g, onPlant) {
    reset();
    focus([]);
    Object.keys(g.plants).forEach((id) => {
      const p = byPlant[id];
      if (!p) return;
      plantDots.filter((d) => d === p).classed("hit", true).style("cursor", "pointer").on("click", () => onPlant && onPlant(id));
      p.halo = 14;
      halos.filter((d) => d === p).classed("hit", true).style("opacity", 0.55);
    });
    g.suppliers.map((id) => meta.suppliers[id]).filter((s) => s && xy(s.city)).forEach((s) => {
      const raw = xy(s.city), p = inside(raw) ? raw : pin(raw), right = p[0] > W * 0.7;
      supplierG.append("circle").attr("class", "supplier").attr("cx", p[0]).attr("cy", p[1]).attr("r", 5)
        .on("mousemove", (ev) => show(`${esc(s.name)}<small>Late or defective supplier, ${esc(s.city)}</small>`, ev)).on("mouseleave", hide);
      labelG.append("text").attr("class", "label extra").attr("x", p[0] + (right ? -9 : 9)).attr("y", p[1] - 8)
        .attr("text-anchor", right ? "end" : "start").text(inside(raw) ? s.name : `${s.name} (${s.city})`);
    });
    g.transfers.forEach((t, i) => byPlant[t.from] && byPlant[t.to] && draw(curve(byPlant[t.from].p, byPlant[t.to].p, 0.3), "move", 2, 600, i * 120));
    dealers.forEach((d) => {
      const c = g.dealers[d.id];
      if (!c) return;
      const n = (c.orders || 0) + (c.stopped || 0) + (c.owners || 0);
      d.r = 2.6 + Math.min(9, Math.sqrt(n) * 1.1);
      d.info = [c.orders && `${c.orders} order delays`, c.loaners && `${c.loaners} loaners`, c.stopped && `${c.stopped} cars stopped`, c.owners && `${c.owners} owners contacted`].filter(Boolean).join(", ");
    });
    dealerDots.classed("safe", (d) => !!g.dealers[d.id]);
    scaleMarks();
    declutter();
  }

  function idle() {
    reset();
    const me = run;
    const beat = () => {
      if (me !== run) return;
      linkG.selectAll("path").transition().duration(600).style("opacity", 0).remove();
      dealerDots.classed("hit safe", false);
      const src = plants[Math.floor(Math.random() * plants.length)];
      halos.filter((d) => d === src).classed("hit", true).call((s) => pulse(s, "hit"));
      const near = [...dealers].sort((a, b) => d3.geoDistance(coords[a.city], coords[src.city]) - d3.geoDistance(coords[b.city], coords[src.city])).slice(1, 9);
      near.forEach((d, i) => {
        draw(curve(src.p, d.p), "link", 1.1, 500, 200 + i * 60);
        setTimeout(() => me === run && dealerDots.filter((x) => x === d).classed("hit", true), 600 + i * 60);
        setTimeout(() => me === run && dealerDots.filter((x) => x === d).classed("hit", false).classed("safe", true), 1700 + i * 60);
      });
      setTimeout(() => me === run && linkG.selectAll("path.link").classed("safe", true), 1800);
    };
    beat();
    idleTimer = setInterval(beat, 3400);
  }

  return { ripple, idle, reset, overview, focus: (p) => focus(p), destroy: () => { reset(); el.innerHTML = ""; } };
}
