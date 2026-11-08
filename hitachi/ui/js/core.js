export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const time = (s) => (s || "").slice(11, 16);

export const TOOL = { "mes.reschedule": "Builds rescheduled", "mes.transfer": "Builds transferred", "dealer.notify": "Dealers notified",
  "crm.assign_loaner": "Loaner cars", "quality.hold_lot": "Lots held", "dealer.stop_sale": "Stop sale orders",
  "crm.notify_customer": "Owners contacted", "escalate": "Escalated" };
export const SOURCE = { "daily digest": "DD", "ops chat": "OC", "quality bulletin": "QB", "plant alert": "PA",
  "news wire": "NW", "supplier email": "SE", simulated: "YOU" };
export const ICON = {
  ok: '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M2.5 6.2l2.3 2.3 4.7-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  no: '<svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  act: '<svg width="18" height="18" viewBox="0 0 20 20"><path d="M11 2L4 11h5l-1 7 7-9h-5l1-7z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
  escalate: '<svg width="18" height="18" viewBox="0 0 20 20"><circle cx="10" cy="7" r="3.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M4 17c1-3.2 3.3-4.8 6-4.8s5 1.6 6 4.8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  ignore: '<svg width="18" height="18" viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M5.5 14.5l9-9" stroke="currentColor" stroke-width="1.6"/></svg>',
};

const svg = (d) => `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
export const IC = {
  home: svg('<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>'),
  alert: svg('<path d="M12 3l9.5 17h-19z"/><path d="M12 10v4"/><path d="M12 17h.01"/>'),
  network: svg('<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="8" r="2.5"/><circle cx="9" cy="18" r="2.5"/><path d="M8.2 7.2l7.4 1.2M7 8.3l1.6 7.3M16.6 10.1l-5.8 6"/>'),
  chart: svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
  layers: svg('<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>'),
  game: svg('<rect x="2" y="7" width="20" height="11" rx="5"/><path d="M7 11v3M5.5 12.5h3"/><circle cx="16" cy="11.5" r=".8"/><circle cx="18" cy="13.5" r=".8"/>'),
  help: svg('<circle cx="12" cy="12" r="9"/><path d="M9.5 9.3a2.6 2.6 0 015 .9c0 1.7-2.5 2.2-2.5 3.8"/><path d="M12 17h.01"/>'),
  car: svg('<path d="M5 17h14M6 17v2M18 17v2"/><path d="M4 13l2-5h12l2 5v4H4z"/><circle cx="8" cy="14" r=".9"/><circle cx="16" cy="14" r=".9"/>'),
  msg: svg('<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>'),
  stack: svg('<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 12.5l9 5 9-5"/><path d="M3 17l9 5 9-5"/>'),
  calendar: svg('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/><path d="M9 15l2 2 4-4"/>'),
  shield: svg('<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>'),
  bolt: svg('<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>'),
  truck: svg('<path d="M2 6h12v10H2zM14 10h4l3 3v3h-7"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="17.5" cy="17.5" r="1.8"/>'),
  cog: svg('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>'),
  users: svg('<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5"/><path d="M16 4.7a3.5 3.5 0 010 6.6M18 14.8c2 .8 3.2 2.5 3.6 5.2"/>'),
  store: svg('<path d="M3 9l2-5h14l2 5"/><path d="M4 9v11h16V9"/><path d="M3 9h18"/><path d="M9 20v-6h6v6"/>'),
  factory: svg('<path d="M3 21V10l5 3V10l5 3V10l5 3V5h3v16z"/><path d="M7 17h2M12 17h2M17 17h1"/>'),
  build: svg('<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 9h16M9 9v11"/>'),
  user: svg('<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4.2 4.1-6.5 8-6.5s7 2.3 8 6.5"/>'),
  play: svg('<circle cx="12" cy="12" r="9"/><path d="M10 8.5l5.5 3.5-5.5 3.5z"/>'),
  send: svg('<path d="M4 12l16-8-6 16-2.5-6.5z"/>'),
  check: svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
  expand: svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
  collapse: svg('<path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/>'),
};

export const STATUS = { resolved: "Resolved", verified: "Not sent", review: "Needs review", ignored: "Ignored", blocked: "Blocked", partial: "Partial", failed: "Failed" };
export const RULES = [
  ["Late part", "When a part shipment is late, every build that needs that part at that plant, between the old and new arrival dates, is affected."],
  ["Plant down", "When a plant is down, every build scheduled there on those days is affected. The plant restarts the next working day."],
  ["Rescheduling", "Each affected build moves to the earliest free slot at the same plant after the disruption. Only if the plant is full is it moved to another plant that builds the same model."],
  ["Dealers", "Every dealer with a delayed customer order gets exactly one notice, listing only their delayed orders."],
  ["Loaner cars", "Platinum, then Gold customers get a loaner from their dealer's pool, earliest promised date first. Standard customers do not."],
  ["Quality hold", "A defective lot is held. Unsold cars built with it are stopped from sale, and owners of sold cars are contacted."],
  ["Noise", "Messages that are not about parts, plants or quality get no action at all."],
  ["Unclear reports", "Rumors or reports without a part, plant or dates are sent for review. Nothing is changed."],
  ["Completeness", "A real incident should end with at least three kinds of action, unless no customer is owed a loaner."],
  ["Do no harm", "Nothing unaffected is touched, and every action must succeed in a rehearsal before it is sent."],
];
export const pill = (s) => `<span class="pill st-${s}">${STATUS[s] || s}</span>`;

export function kind(e) {
  if (e.classification === "Noise") return "noise";
  if (e.classification === "Unconfirmed Report") return "escalated";
  return "incident";
}

export function title(c) {
  if (c.startsWith("Compound")) return "Compound incident";
  return { Noise: "Not operational", "Unconfirmed Report": "Unconfirmed report" }[c] || c.charAt(0) + c.slice(1).toLowerCase();
}

export async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
}

const cache = {};
export const overview = () => (cache.overview ||= api("/api/overview"));
export const eventDetail = (id) => (cache[id] ||= api(`/api/event/${encodeURIComponent(id)}`));
export function forget() { Object.keys(cache).forEach((k) => delete cache[k]); }

export function highlight(text, incidents) {
  const marks = [];
  incidents.forEach((r) => Object.entries(r.resolution).forEach(([field, v]) => {
    if (v && v.mention) marks.push({ mention: v.mention, tip: `${field.replace(/_/g, " ")}: ${v.id || v.date} (${v.via || v.rule})` });
  }));
  let out = esc(text);
  marks.sort((a, b) => b.mention.length - a.mention.length).forEach((m) => {
    const needle = esc(m.mention).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(`(?<![\\w>])(${needle})(?![^<]*<\\/mark>)`, "i"), (hit) => `<mark class="ent" data-tip="${esc(m.tip)}">${hit}</mark>`);
  });
  return out;
}
