import { $, $$, IC, api, esc, forget } from "./core.js";
import audit from "./audit.js";
import board from "./board.js";
import explorer from "./explorer.js";
import help from "./help.js";
import ops from "./ops.js";
import play from "./play.js";
import { startTour } from "./tour.js";
import tower from "./tower.js";

const SECTIONS = [
  ["ops", "Operations", IC.home, ops, "What is happening right now"],
  ["incidents", "Incidents", IC.alert, tower, "Work one incident: the message, its impact, the actions and the checks"],
  ["network", "Supply network", IC.network, explorer, "Search any record and follow how it is connected"],
  ["analytics", "Analytics", IC.chart, board, "The whole morning on one screen"],
  ["evidence", "Evidence", IC.layers, audit, "Every action and every policy check, ready for audit"],
  ["simulation", "Simulation", IC.game, play, "Practice triage on the morning's real messages"],
  ["help", "Help", IC.help, help, "How to use Ripple Radar"],
];
const ALIAS = { tower: "incidents", explorer: "network", board: "analytics", audit: "evidence", play: "simulation" };
const EXAMPLES = ["The Texas plant loses power next Wednesday and Thursday.",
  "Lumen says the battery packs for Huntsville due Monday Mar 22 now land Wednesday Mar 24.",
  "A shipping container had an accident in Kansas.", "Heard chip supply might get tight soon, nothing official."];
const SCENARIOS = [["Rumor", "Someone heard there might be a problem with a supplier next week."],
  ["Date conflict", "The Princeton plant is closed Monday, Mar 23 and Tuesday, Mar 24."],
  ["Outside network", "A plant in Kansas lost power today."],
  ["No capacity", "The Princeton and Greensboro plants are both shut from Monday Mar 8 through Friday Apr 2."]];
let page;

$("#sideNav").innerHTML = SECTIONS.map(([k, name, ic]) => `<a href="#/${k}" data-route="${k}">${ic}<span>${name}</span><small data-badge="${k}"></small></a>`).join("");
$$("[data-ic]").forEach((el) => { el.outerHTML = IC[el.dataset.ic] || ""; });

async function route() {
  let [name = "", ...rest] = location.hash.replace(/^#\/?/, "").split("/");
  name = ALIAS[name] || name || "ops";
  const section = SECTIONS.find(([k]) => k === name);
  page?.leave?.();
  const view = $("#view");
  view.innerHTML = "";
  page = section ? section[3] : ops;
  document.body.classList.toggle("locked", [ops, tower, explorer, play].includes(page));
  $$(".side-nav a").forEach((a) => a.classList.toggle("on", a.dataset.route === name));
  document.title = section ? `${section[1]} | Ripple Radar` : "Ripple Radar";
  window.scrollTo(0, 0);
  try {
    await page.enter(view, rest.length ? decodeURIComponent(rest.join("/")) : undefined);
    if (page === ops) startTour();
  } catch (err) { view.innerHTML = `<p class="placeholder error">Could not load this screen: ${esc(err.message)}</p>`; }
}

export async function send(text) {
  const d = await api("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  forget();
  if (page === tower) await tower.refresh(d.event_id);
  else location.hash = `#/incidents/${encodeURIComponent(d.event_id)}`;
  return d;
}

const pretty = (name) => {
  const [fam, size] = name.split(":");
  return `${esc(fam.replace(/^qwen/i, "Qwen").replace(/^llama/i, "Llama").replace(/^phi/i, "Phi").replace(/^gemma/i, "Gemma"))}${size ? ` &middot; ${esc(size.toUpperCase())}` : ""}`;
};

function paint(h) {
  $("#model").innerHTML = `<i class="dot ${h.online ? "" : "off"}"></i>${IC.stack}${pretty(h.model)} <span class="faint">${h.online ? "Local" : "Offline"}</span>`;
  $("#model").title = h.online ? "Running on this computer. Click to switch model." : "The local model is not running. Start Ollama.";
  $("#simModel").textContent = h.online ? `${h.model} · local` : `${h.model} is not running. Start Ollama.`;
  $("#modelMenu").innerHTML = (h.models.length ? h.models.map((m) => `<button role="option" data-m="${esc(m.name)}" aria-selected="${m.name === h.model}">
      <span><b>${pretty(m.name)}</b><span>${m.gb} GB, on this computer</span></span>${m.name === h.model ? `<span class="check">${IC.check}</span>` : ""}</button>`).join("")
    : `<p style="border:0">Ollama is not running, so no local models are available.</p>`) +
    `<p>All models run locally. Add one with <code>ollama pull llama3.2:3b</code></p>`;
  $$("#modelMenu [data-m]").forEach((b) => b.onclick = async () => {
    menu(false);
    paint(await api("/api/model", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: b.dataset.m }) }));
  });
}

function menu(open) {
  $("#modelMenu").hidden = !open;
  $("#model").setAttribute("aria-expanded", String(open));
}

async function health() {
  paint(await api("/api/health").catch(() => ({ online: false, model: "local model", models: [] })));
}

$("#model").onclick = (e) => { e.stopPropagation(); menu($("#modelMenu").hidden); };
document.addEventListener("click", (e) => { if (!e.target.closest(".model-wrap")) menu(false); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") menu(false); });

$("#simExamples").innerHTML = EXAMPLES.map((x, i) => `<button type="button" class="chip" data-i="${i}">${esc(x.length > 42 ? x.slice(0, 40) + "..." : x)}</button>`).join("");
$$("#simExamples .chip").forEach((b) => b.onclick = () => { $("#simText").value = EXAMPLES[b.dataset.i]; $("#simText").focus(); });
$("#simTricks").innerHTML = SCENARIOS.map(([l, x], i) => `<button type="button" class="chip trick" data-i="${i}" title="${esc(x)}">${esc(l)}</button>`).join("");
$$("#simTricks .chip").forEach((b) => b.onclick = () => { $("#simText").value = SCENARIOS[b.dataset.i][1]; $("#simText").focus(); });
$("#simOpen").onclick = () => { $("#simMsg").textContent = ""; $("#sim").showModal(); $("#simText").focus(); };
$("#simRun").onclick = async (e) => {
  e.preventDefault();
  const text = $("#simText").value.trim();
  if (!text) return $("#simText").focus();
  $("#simRun").disabled = true;
  $("#simMsg").textContent = "Analyzing...";
  try { await send(text); $("#sim").close(); $("#simText").value = ""; }
  catch (err) { $("#simMsg").innerHTML = `<span class="error">${esc(err.message)}</span>`; }
  $("#simRun").disabled = false;
};

health();
setInterval(health, 30000);
window.addEventListener("hashchange", route);
route();
