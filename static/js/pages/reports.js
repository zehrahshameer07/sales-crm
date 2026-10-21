import { api, download, errorText } from "../api.js";
import { isLead, state } from "../state.js";
import { STATUS, TYPE, addDays, appToday, avatar, card, emptyState, field, formatDays, h, hbars, icon, percentBar, roleBadge, select, skeletons, toast } from "../ui.js";

const filters = { from: "", to: "", status: "", activity_type: "", owner_id: "", preset: "month" };

function applyPreset(name) {
  const today = appToday();
  filters.preset = name;
  if (name === "week") { const d = new Date(`${today}T00:00:00`); filters.from = addDays(today, -((d.getDay() + 6) % 7)); filters.to = today; }
  else if (name === "month") { filters.from = `${today.slice(0, 8)}01`; filters.to = today; }
  else if (name === "30") { filters.from = addDays(today, -29); filters.to = today; }
  else if (name === "all") { filters.from = ""; filters.to = ""; }
}
if (!filters.from) applyPreset("month");

export async function render(root) {
  const preview = h("div", { class: "stack" }, skeletons(2, 120));
  const params = () => ({ from: filters.from, to: filters.to, status: filters.status, activity_type: filters.activity_type, owner_id: filters.owner_id });

  const presets = [["week", "This week"], ["month", "This month"], ["30", "Last 30 days"], ["all", "All time"]];
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Date range" }, presets.map(([key, label]) =>
    h("button", { type: "button", "aria-pressed": String(filters.preset === key), text: label, on: { click: () => { applyPreset(key); render(root); } } })));
  const from = h("input", { id: "r-from", class: "input", type: "date", value: filters.from, max: appToday() });
  const to = h("input", { id: "r-to", class: "input", type: "date", value: filters.to, max: appToday() });
  const status = select("r-status", [["", "Any status"], ...Object.entries(STATUS)], filters.status);
  const type = select("r-type", [["", "Any type"], ...Object.entries(TYPE)], filters.activity_type);
  const owner = isLead() ? select("r-owner", [["", state.user.role === "admin" ? "Everyone" : "Whole team"], ...state.options.map((p) => [p.id, p.full_name])], filters.owner_id) : null;

  const refresh = () => {
    filters.from = from.value; filters.to = to.value; filters.status = status.value; filters.activity_type = type.value; filters.owner_id = owner?.value || "";
    filters.preset = "custom"; seg.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", "false"));
    loadPreview();
  };
  [from, to, status, type, owner].forEach((el) => el && el.addEventListener("change", refresh));

  async function save(kind, button) {
    button.disabled = true;
    try {
      await download(`/api/reports/activities.${kind}`, params(), `sales-${kind === "pdf" ? "report" : "activities"}-${appToday()}.${kind}`);
      toast(`${kind.toUpperCase()} downloaded`);
    } catch (error) { toast(errorText(error), "error"); } finally { button.disabled = false; }
  }
  const csvBtn = h("button", { class: "btn", type: "button", on: { click: () => save("csv", csvBtn) } }, icon("download"), "Download CSV");
  const pdfBtn = h("button", { class: "btn primary", type: "button", on: { click: () => save("pdf", pdfBtn) } }, icon("file"), "Download PDF");

  async function loadPreview() {
    preview.replaceChildren(...skeletons(2, 120));
    try {
      const r = await api("/api/reports/summary", { params: params() });
      const ov = r.overview;
      const stat = (label, value) => h("div", { class: "card kpi" }, h("div", {}, h("div", { class: "num", text: String(value) }), h("div", { class: "lbl", text: label })));
      const blocks = [
        h("div", { class: "grid cols-4" }, stat("Activities", ov.total), stat("Completed", `${ov.completed} (${ov.completion_rate}%)`),
          stat("Avg. days to complete", ov.durations.avg_days_to_complete ?? "–"), stat("Overdue follow-ups", ov.follow_ups.overdue)),
        h("div", { class: "grid cols-2" }, card("By status", hbars(r.by_status, STATUS)), card("By activity type", hbars(ov.by_type, TYPE))),
      ];
      if (r.by_employee.length) {
        const cols = "minmax(0,2fr) 80px 90px 110px minmax(0,1.3fr) 90px";
        blocks.push(card("By employee", h("div", { class: "table", style: { "--cols": cols } },
          h("div", { class: "th" }, ["Employee", "Total", "Pending", "Completed", "Completion", "Avg days"].map((t, i) => h("span", { class: i && i !== 4 ? "num" : "", text: t }))),
          r.by_employee.map((e) => h("div", { class: "tr" },
            h("div", { class: "td name cell-person" }, avatar(e.full_name, "sm"), h("span", { class: "strong ellipsis", text: e.full_name })),
            h("div", { class: "td num", "data-label": "Total", text: String(e.total) }), h("div", { class: "td num", "data-label": "Pending", text: String(e.pending + e.in_progress) }),
            h("div", { class: "td num", "data-label": "Completed", text: String(e.completed) }), h("div", { class: "td", "data-label": "Completion" }, percentBar(e.completion_rate)),
            h("div", { class: "td num", "data-label": "Avg days", text: e.avg_days_to_complete ?? "–" }))))));
      }
      preview.replaceChildren(...blocks);
    } catch (error) { preview.replaceChildren(h("div", { class: "card" }, h("p", { class: "error-text", text: errorText(error) }))); }
  }

  root.replaceChildren(h("div", { class: "page" },
    h("div", { class: "page-head" }, h("div", {}, h("h2", { text: "Reports" }), h("p", { text: `${state.user.role === "admin" ? "Company-wide" : state.user.role === "manager" ? "Your team" : "Your"} activity summary. Export it as CSV or PDF.` })),
      h("div", { class: "row wrap" }, csvBtn, pdfBtn)),
    h("section", { class: "card stack" },
      seg,
      h("div", { class: "form-grid", style: { gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" } },
        field("From (start date)", from), field("To", to), field("Status", status), field("Type", type), owner && field("Salesperson", owner))),
    preview));
  loadPreview();
}
