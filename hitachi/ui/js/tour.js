import { $ } from "./core.js";

const STEPS = [
  ["#kpis", "Key figures", "Select a figure to open the records behind it."],
  ["#hub", "Impact analysis", "The affected plant is in the center: causes on the left, downstream records on the right."],
  ["#incList", "Incidents", "Needs review first, then resolved. Select one to update the impact view."],
  ["#simOpen", "New event", "Paste a message to analyze it against the policy rules."],
  [".side-nav", "Navigation", "Incidents for details, Evidence for the action log, Help for the guide."],
];
const seen = () => { try { return localStorage.getItem("rr-tour") === "done"; } catch { return true; } };
const done = () => { try { localStorage.setItem("rr-tour", "done"); } catch { } };

export function startTour(force = false) {
  if (!force && seen()) return;
  const box = $("#tour");
  let i = 0;
  const show = () => {
    const [sel, h, p] = STEPS[i], el = $(sel);
    if (!el) { close(); return; }
    const r = el.getBoundingClientRect(), right = r.left + r.width / 2 > innerWidth / 2;
    const top = Math.min(innerHeight - 190, Math.max(16, r.bottom + 14 > innerHeight - 190 ? r.top - 190 : r.bottom + 14));
    const left = Math.min(innerWidth - 340, Math.max(16, right ? r.right - 320 : r.left));
    box.innerHTML = `<div class="tour-ring" style="left:${r.left - 6}px;top:${r.top - 6}px;width:${r.width + 12}px;height:${r.height + 12}px"></div>
      <div class="tour-card" style="left:${left}px;top:${top}px"><h4>${h}</h4><p>${p}</p>
      <div class="foot"><span>${i + 1} of ${STEPS.length}</span><button class="btn" id="tourSkip">Skip</button>
      <button class="btn btn-primary" id="tourNext">${i + 1 < STEPS.length ? "Next" : "Done"}</button></div></div>`;
    $("#tourSkip").onclick = close;
    $("#tourNext").onclick = () => { i += 1; if (i < STEPS.length) show(); else close(); };
    $("#tourNext").focus();
  };
  const close = () => { box.hidden = true; box.innerHTML = ""; done(); };
  box.hidden = false;
  show();
}
