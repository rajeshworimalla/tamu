import { $, $$, ICON, TOOL, api, esc, pill } from "./core.js";

const RULES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];
const RULE_NAME = { 1: "Delay", 2: "Outage", 3: "Reschedule", 4: "Dealers", 5: "Loaners", 6: "Quality", 7: "Noise", 8: "Unclear", 9: "Complete", 10: "Untouched" };
let data, rows, f = { event: "", tool: "", agent: "", q: "", only: "" }, limit = 200;

function log() {
  const q = f.q.toLowerCase();
  const list = rows.filter((r) => (!f.event || r.event === f.event) && (!f.tool || r.tool === f.tool) && (!f.agent || r.agent === f.agent)
    && (!f.only || (f.only === "failed" ? !r.ok : f.only === "sent" ? r.sent : f.only === "unsent" ? r.tool !== "none" && !r.sent : f.only === "escalate" ? r.tool === "escalate" : f.only === "none" ? r.tool === "none" : true))
    && (!q || `${r.target} ${r.reason} ${r.event}`.toLowerCase().includes(q)));
  $("#logCount").textContent = `${list.length} ROWS`;
  $("#logBody").innerHTML = list.slice(0, limit).map((r) => `<tr><td class="m faint">${String(r.i).padStart(3, "0")}</td>
    <td class="m"><a href="#/incidents/${encodeURIComponent(r.event)}">${esc(r.event)}</a></td><td>${esc(r.agent)}</td>
    <td class="m">${r.tool === "none" ? "no action" : esc(TOOL[r.tool] || r.tool)}</td><td class="m">${esc(r.target)}</td><td class="m">${esc(r.rule)}</td>
    <td class="m" style="color:${r.ok ? "var(--ok)" : "var(--crit)"}">${r.ok ? "PASS" : "FAIL"}</td>
    <td class="m" style="color:${r.sent ? "var(--ok)" : "var(--faint)"}">${r.tool === "none" ? "" : r.sent ? "ACCEPTED" : "NOT SENT"}</td><td class="faint">${esc(r.reason)}</td></tr>`).join("")
    || `<tr><td colspan="9" class="placeholder">No rows match</td></tr>`;
  $("#more").style.display = list.length > limit ? "" : "none";
  $("#more").textContent = `Show all ${list.length}`;
}

function select(id, values, label) {
  return `<select data-k="${id}"><option value="">${label}</option>${values.map((v) => `<option value="${esc(v)}">${esc(TOOL[v] || v)}</option>`).join("")}</select>`;
}

export default {
  async enter(el, param) {
    const [pk, pv] = (param || "").split("=");
    if (pk in f) f[pk] = pv || "";
    el.innerHTML = `<section class="audit">
      <div class="pane"><div class="pane-head"><span class="code">01</span><h2>Execution summary</h2><span class="right label">Select a figure to filter the log</span></div><div class="tele" id="tele"></div></div>
      <div class="pane"><div class="pane-head"><span class="code">02</span><h2>Policy check matrix</h2><span class="right label">Recomputed from source data</span></div><div class="matrix" id="matrix"></div></div>
      <div class="pane"><div class="pane-head"><span class="code">03</span><h2>Action log</h2><span class="label" id="logCount"></span><div class="right filters" id="filters"></div></div>
        <div style="overflow:auto"><table class="log"><thead><tr><th>#</th><th>Event</th><th>Agent</th><th>Action</th><th>Target</th><th>Rule</th><th>Rehearsal</th><th>Server</th><th>Reason</th></tr></thead>
        <tbody id="logBody"></tbody></table></div><div style="padding:10px;text-align:center"><button class="btn" id="more">Show all</button></div></div>
    </section>`;
    data = await api("/api/audit");
    const ev = data.events;
    rows = data.rows.map((r) => ({ ...r }));
    ev.filter((e) => e.status === "ignored").forEach((e) => rows.push({ event: e.event_id, tool: "none", agent: "Coordinator", rule: "7", target: "nothing touched", reason: e.summary, ok: true }));
    rows.sort((a, b) => a.event.localeCompare(b.event, undefined, { numeric: true }) || (a.n ?? 0) - (b.n ?? 0)).forEach((r, i) => { r.i = i + 1; });
    const checks = Object.values(data.matrix).flatMap((m) => Object.values(m));
    const sentOk = data.rows.filter((r) => r.sent).length;
    const tiles = [["", "Events", ev.length], ["", "Actions planned", data.rows.length], ["failed", "Failed in rehearsal", data.rows.filter((r) => !r.ok).length],
      ["sent", "Accepted by server", `${sentOk}<small class="faint" style="font-size:14px"> / ${data.rows.length}</small>`],
      ["", "Policy checks passed", `${checks.filter(Boolean).length}<small class="faint" style="font-size:14px"> / ${checks.length}</small>`],
      ["escalate", "Escalated", data.rows.filter((r) => r.tool === "escalate").length], ["none", "Ignored", ev.filter((e) => e.status === "ignored").length]];
    $("#tele").innerHTML = tiles.map(([k, l, v]) => `<button data-only="${k}"><span class="label">${l}</span><b>${v}</b></button>`).join("");
    $$("#tele button").forEach((b) => b.onclick = () => { f.only = f.only === b.dataset.only ? "" : b.dataset.only; $$("#tele button").forEach((x) => x.classList.toggle("on", f.only && x.dataset.only === f.only)); log(); });
    $("#matrix").innerHTML = `<table><thead><tr><th></th><th></th>${RULES.map((r) => `<th title="Handbook rule ${r}">R${r}<br><span style="font-size:9px">${RULE_NAME[r].toUpperCase()}</span></th>`).join("")}</tr></thead><tbody>${ev.map((e) =>
      `<tr><th class="ev" data-ev="${esc(e.event_id)}">${esc(e.event_id)}</th><th style="text-align:left">${pill(e.status)}</th>${RULES.map((r) => {
        const v = data.matrix[e.event_id]?.[r];
        return v === undefined ? `<td class="na">&middot;</td>` : `<td class="${v ? "ok" : "no"}">${v ? ICON.ok : ICON.no}</td>`;
      }).join("")}</tr>`).join("")}</tbody></table>`;
    $$("#matrix th.ev").forEach((t) => t.onclick = () => { f.event = f.event === t.dataset.ev ? "" : t.dataset.ev; $("select[data-k=event]").value = f.event; log(); });
    $("#filters").innerHTML = select("event", ev.map((e) => e.event_id), "All events") + select("agent", [...new Set(rows.map((r) => r.agent))], "All agents")
      + select("tool", [...new Set(data.rows.map((r) => r.tool))], "All actions") + `<input data-k="q" placeholder="Search target or reason">`;
    $$("#filters [data-k]").forEach((x) => { x.value = f[x.dataset.k] || ""; });
    $$("#filters [data-k]").forEach((x) => x.oninput = () => { f[x.dataset.k] = x.value; limit = 200; log(); });
    $("#more").onclick = () => { limit = Infinity; log(); };
    log();
  },
  leave() { f = { event: "", tool: "", agent: "", q: "", only: "" }; limit = 200; },
};
