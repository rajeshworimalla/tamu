import { esc } from "./core.js";

const STAGE = { Supplier: 1, Part: 1, Model: 2, ProductionOrder: 3, Plant: 3, CustomerOrder: 4, Vehicle: 4, Dealer: 5, Customer: 5 };
const NAME = { 1: "Parts", 2: "Models", 3: "Builds", 5: "People" };

function columns(r) {
  const hide = new Set(r.nodes.filter((n) => n.type === "Plant" && n.layer !== 0).map((n) => n.id));
  const nodes = r.nodes.filter((n) => !hide.has(n.id)).map((n) => ({ ...n, layer: n.layer === 0 ? 0 : STAGE[n.type] ?? 3 }));
  const edges = r.edges.filter((e) => !hide.has(e.source) && !hide.has(e.target));
  const cols = {};
  nodes.forEach((n) => (cols[n.layer] ||= []).push(n));
  const name = (k) => (k === 0 ? "Source" : k === 4 ? (cols[4].some((n) => n.type === "Vehicle") ? "Vehicles" : "Orders") : NAME[k]);
  const list = Object.keys(cols).map(Number).sort((a, b) => a - b)
    .map((k) => ({ key: k, name: name(k), nodes: cols[k].sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true })) }));
  return { nodes, edges, list };
}

export function drawFlow(el, d, onNode) {
  const { nodes, edges, list } = columns(d.ripple);
  el.innerHTML = `<svg class="flow-heads" style="position:absolute;inset:0;width:100%;height:100%"></svg><div class="flow-cy" style="position:absolute;inset:0"></div>`;
  const heads = el.querySelector(".flow-heads"), box = el.querySelector(".flow-cy");
  const W = el.clientWidth, H = el.clientHeight, padX = 90, top = 64, bottom = 32, pos = {};
  const step = list.length > 1 ? (W - 2 * padX) / (list.length - 1) : 0;
  list.forEach((c, i) => {
    const k = c.nodes.length, gap = Math.min(60, (H - top - bottom) / Math.max(k, 1));
    c.x = list.length > 1 ? padX + i * step : W / 2;
    c.nodes.forEach((n, j) => { pos[n.id] = { x: c.x, y: top + (H - top - bottom) / 2 + (j - (k - 1) / 2) * gap }; });
  });
  const state = {};
  const paintHeads = () => {
    heads.innerHTML = list.map((c, i) => `<line x1="${c.x}" x2="${c.x}" y1="46" y2="${H - 12}" stroke="#1E372E" stroke-dasharray="2 5"/>
      <text x="${c.x}" y="28" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="10.5" font-weight="500" letter-spacing="1.2"
        fill="${state[c.key] === "hit" ? "#E5735A" : state[c.key] === "done" ? "#A5D6B1" : "#6C8478"}">${String(i + 1).padStart(2, "0")} ${esc(c.name.toUpperCase())}</text>`).join("");
  };
  paintHeads();
  const cy = cytoscape({
    container: box, autoungrabify: true, userZoomingEnabled: false, userPanningEnabled: false, layout: { name: "preset", fit: false },
    elements: nodes.map((n) => ({ position: pos[n.id], data: { ...n, size: n.layer === 0 ? 24 : n.count ? Math.min(42, 20 + Math.sqrt(n.count) * 1.8) : n.layer <= 2 ? 15 : 11,
        text: n.layer <= 2 || n.count ? n.label : "", acted: Object.keys(n.tools || {}).length ? 1 : 0 } }))
      .concat(edges.map((e) => ({ data: { id: `${e.source}>${e.target}`, source: e.source, target: e.target } }))),
    style: [
      { selector: "node", style: { width: "data(size)", height: "data(size)", "background-color": "#2B4B3F", label: "data(text)", color: "#D6EEDC",
        "font-family": "Inter, sans-serif", "font-size": 11, "text-valign": "bottom", "text-margin-y": 5, "text-outline-color": "#0F1F1A",
        "text-outline-width": 3, opacity: 0.3, "transition-property": "background-color, opacity", "transition-duration": "300ms" } },
      { selector: "node[layer = 0]", style: { "background-color": "#E5735A", opacity: 1 } },
      { selector: "edge", style: { width: 1, "line-color": "#2B4B3F", "curve-style": "taxi", "taxi-direction": "rightward", opacity: 0.2 } },
      { selector: "node.hit", style: { opacity: 1, "background-color": "#E5735A" } },
      { selector: "node.ctx", style: { opacity: 1, "background-color": "#4E6F61" } },
      { selector: "node.safe", style: { opacity: 1, "background-color": "#A5D6B1" } },
      { selector: "edge.on", style: { opacity: 0.85, "line-color": "#3E5F52" } },
    ],
  });
  cy.on("tap", "node", (e) => onNode && onNode(e.target.data()));
  let timers = [];
  const replay = () => {
    timers.forEach(clearTimeout); timers = [];
    cy.elements().removeClass("hit ctx safe on");
    Object.keys(state).forEach((k) => delete state[k]); paintHeads();
    list.forEach((c, i) => timers.push(setTimeout(() => {
      cy.nodes(`[layer = ${c.key}]`).addClass("hit");
      cy.edges().filter((x) => x.source().hasClass("hit") && x.target().hasClass("hit")).addClass("on");
      state[c.key] = "hit"; paintHeads();
    }, 420 * i)));
    timers.push(setTimeout(() => {
      cy.nodes().forEach((n) => { n.removeClass("hit"); n.addClass(n.data("acted") ? "safe" : "ctx"); });
      list.forEach((c) => { state[c.key] = "done"; }); paintHeads();
    }, 420 * list.length + 300));
  };
  replay();
  return { replay, destroy: () => { timers.forEach(clearTimeout); cy.destroy(); el.innerHTML = ""; } };
}
