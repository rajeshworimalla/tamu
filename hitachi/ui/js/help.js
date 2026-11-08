import { $, IC, RULES, api, esc, overview, pill } from "./core.js";
import { startTour } from "./tour.js";


export default {
  async enter(el) {
    const [o, h] = await Promise.all([overview(), api("/api/health").catch(() => ({ online: false, model: "unknown" }))]);
    el.innerHTML = `<section class="help">
      <div class="pane"><div class="pane-head"><h2>Get started in three steps</h2><div class="right"><button class="btn btn-primary" id="tourBtn">${IC.play} Take the tour</button></div></div>
        <div class="pane-body help-grid">
          <div><span class="tile">${IC.home}</span><h3>1. Check Operations</h3><p>The home screen shows the morning at a glance: five numbers, the ripple of the selected incident, and every active incident.</p></div>
          <div><span class="tile">${IC.alert}</span><h3>2. Open an incident</h3><p>Click any incident to see the original message, what it affects on the map, the before and after schedule, every action and every check.</p></div>
          <div><span class="tile">${IC.send}</span><h3>3. Analyze a new event</h3><p>Press <b>New event</b>, paste the message and choose <b>Analyze event</b>.</p></div>
        </div></div>
      <div class="pane"><div class="pane-head"><h2>What the statuses mean</h2></div><div class="pane-body"><table>
        <tr><td>${pill("resolved")}</td><td>A real disruption. Every action was carried out and accepted by the company systems.</td></tr>
        <tr><td>${pill("verified")}</td><td>A real disruption. The plan is ready and passed every rule in a rehearsal, but it has not been sent to the company systems yet.</td></tr>
        <tr><td>${pill("review")}</td><td>Possibly real but too vague or unconfirmed. A person needs to look. Nothing was changed.</td></tr>
        <tr><td>${pill("ignored")}</td><td>Not about our operations, such as a brochure request. Nothing was touched.</td></tr>
        <tr><td>${pill("blocked")}</td><td>A plan failed a rule check, so nothing was sent and it was handed to a person.</td></tr>
        <tr><td>${pill("partial")}</td><td>Some actions were accepted by the company systems and some were not. A person must finish it.</td></tr>
        <tr><td>${pill("failed")}</td><td>The company systems refused every action, so nothing changed. The reason is shown on the incident.</td></tr></table></div></div>
      <div class="pane"><div class="pane-head"><h2>The ten rules the tower follows</h2><span class="right label">From the operations policy handbook</span></div><div class="pane-body"><table>
        ${RULES.map(([n, d], i) => `<tr><td><b>${i + 1}. ${n}</b></td><td>${d}</td></tr>`).join("")}</table></div></div>
      <div class="pane"><div class="pane-head"><h2>System</h2></div><div class="pane-body"><table>
        <tr><td>Language model</td><td>${esc(h.model)}, running on this computer. ${h.online ? "Online and ready." : "Not running. Start Ollama to read new messages."}</td></tr>
        <tr><td>Company data</td><td>${o.totals.graph_nodes.toLocaleString()} records and ${o.totals.graph_edges.toLocaleString()} links: plants, suppliers, parts, builds, orders, dealers, customers and vehicles.</td></tr>
        <tr><td>Privacy</td><td>Everything runs locally. No message or record leaves the machine.</td></tr></table></div></div>
    </section>`;
    $("#tourBtn").onclick = () => { location.hash = "#/ops"; setTimeout(() => startTour(true), 600); };
  },
};
