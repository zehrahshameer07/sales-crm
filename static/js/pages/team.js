import { api, errorText } from "../api.js";
import { isAdmin, state } from "../state.js";
import { avatar, card, emptyState, h, percentBar, roleBadge, skeletons } from "../ui.js";

let period = "month";
const PERIODS = [["today", "Today"], ["week", "This week"], ["month", "This month"], ["all", "All time"]];

export async function render(root, ctx) {
  const body = h("div", {}, skeletons(1, 240));
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Period" }, PERIODS.map(([value, label]) =>
    h("button", { type: "button", "aria-pressed": String(value === period), text: label, on: { click: () => { period = value; render(root, ctx); } } })));
  root.replaceChildren(h("div", { class: "page" },
    h("div", { class: "page-head" },
      h("div", {}, h("h2", { text: isAdmin() ? "Team performance" : "My team" }), h("p", { text: "Progress per person. Click a row to see their activities." })), seg),
    body));
  try {
    const rows = await api("/api/stats/team", { params: { period } });
    const cols = isAdmin() ? "minmax(0,1.6fr) 110px minmax(0,1.2fr) 70px 70px 70px 70px minmax(0,1.2fr) 70px 80px"
      : "minmax(0,1.6fr) 110px 70px 70px 70px 70px minmax(0,1.2fr) 70px 80px";
    const go = (r) => { state.activityPreset = { owner_id: r.user_id, period }; ctx.navigate("activities"); };
    const heads = ["Employee", "Role", ...(isAdmin() ? ["Manager"] : []), "Total", "Pending", "In prog.", "Done", "Completion", "Avg days", "Overdue"];
    const table = h("div", { class: "table", style: { "--cols": cols } },
      h("div", { class: "th" }, heads.map((t, i) => h("span", { class: i >= (isAdmin() ? 3 : 2) && t !== "Completion" ? "num" : "", text: t }))),
      rows.length ? rows.map((r) => h("div", { class: "tr clickable", tabindex: "0", role: "button", on: { click: () => go(r), keydown: (e) => { if (e.key === "Enter") go(r); } } },
        h("div", { class: "td name cell-person" }, avatar(r.full_name), h("div", {}, h("div", { class: "strong ellipsis", text: r.is_self ? `${r.full_name} (you)` : r.full_name }), h("div", { class: "tiny muted", text: r.region || "" }))),
        h("div", { class: "td", "data-label": "Role" }, roleBadge(r.role)),
        isAdmin() && h("div", { class: "td", "data-label": "Manager", text: r.manager_name || "–" }),
        h("div", { class: "td num", "data-label": "Total", text: String(r.total) }),
        h("div", { class: "td num", "data-label": "Pending", text: String(r.pending) }),
        h("div", { class: "td num", "data-label": "In progress", text: String(r.in_progress) }),
        h("div", { class: "td num", "data-label": "Completed", text: String(r.completed) }),
        h("div", { class: "td", "data-label": "Completion" }, percentBar(r.completion_rate)),
        h("div", { class: "td num", "data-label": "Avg days", text: r.avg_days_to_complete === null ? "–" : String(r.avg_days_to_complete) }),
        h("div", { class: "td num", "data-label": "Overdue" }, r.follow_ups_overdue ? h("span", { class: "chip bad", text: String(r.follow_ups_overdue) }) : "0")))
        : emptyState("Nobody here yet", "Team members appear once an admin assigns them to you."));
    body.replaceChildren(card("", table));
  } catch (error) {
    body.replaceChildren(h("div", { class: "card" }, h("p", { class: "error-text", text: errorText(error) })));
  }
}
