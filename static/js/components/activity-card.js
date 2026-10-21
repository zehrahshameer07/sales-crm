import { isLead } from "../state.js";
import { PRODUCT, TYPE, appToday, avatar, formatDay, formatDays, h, icon, statusBadge, timeAgo, fullDateTime } from "../ui.js";
import { openActivityForm } from "./activity-form.js";
import { changeStatus, showHistory } from "./status.js";

function followUpChip(a) {
  if (!a.follow_up_date || a.status === "completed") return null;
  const today = appToday();
  const kind = a.follow_up_date < today ? "bad" : a.follow_up_date === today ? "warn" : "";
  const label = a.follow_up_date < today ? "Follow-up overdue" : "Follow-up";
  return h("span", { class: `chip ${kind}`, title: a.follow_up_notes || "" }, icon("calendar", "sm"), `${label}: ${formatDay(a.follow_up_date)}`);
}

/** One activity. `reload` re-fetches the list after a change. */
export function activityCard(a, reload, { showOwner = isLead() } = {}) {
  const next = [];
  if (a.permissions.can_change_status) {
    if (a.status === "pending") next.push(["in_progress", "Start work"]);
    next.push(["completed", "Mark completed"]);
  }
  const actions = h("div", { class: "a-actions" },
    a.permissions.can_edit && h("button", { class: "btn sm", type: "button", on: { click: async () => { if (await openActivityForm(a)) reload(); } } }, icon("edit", "sm"), "Edit"),
    next.map(([status, label]) => h("button", { class: `btn sm ${status === "completed" ? "soft" : ""}`, type: "button",
      on: { click: async () => { if (await changeStatus(a, status)) reload(); } } }, icon(status === "completed" ? "check" : "clock", "sm"), label)),
    h("button", { class: "btn sm", type: "button", on: { click: () => showHistory(a) } }, icon("history", "sm"), "History"),
    a.status === "completed" && !a.permissions.can_edit && h("span", { class: "tiny muted row" }, icon("lock", "sm"), "Locked"));

  return h("article", { class: "card activity" },
    avatar(a.owner.full_name),
    h("div", { class: "grow" },
      h("div", { class: "a-top" },
        h("div", { class: "grow" }, h("h3", { class: "a-name ellipsis", text: a.customer_name }),
          showOwner && h("div", { class: "small muted", text: a.owner.full_name })),
        statusBadge(a.status)),
      h("div", { class: "a-chips" },
        h("span", { class: "chip" }, TYPE[a.activity_type]),
        a.product_interested && h("span", { class: "chip" }, PRODUCT[a.product_interested]),
        a.location && h("span", { class: "chip" }, a.location),
        a.contact && h("span", { class: "chip" }, a.contact),
        followUpChip(a)),
      a.notes && h("p", { class: "a-notes", text: a.notes }),
      h("div", { class: "a-meta" },
        h("span", {}, icon("calendar", "sm"), `Started ${formatDay(a.start_date)}`),
        a.end_date && h("span", {}, icon("check", "sm"), `Completed ${formatDay(a.end_date)} · ${a.days_to_complete === 0 ? "same day" : `took ${formatDays(a.days_to_complete)}`}`),
        h("span", { title: fullDateTime(a.updated_at) }, icon("clock", "sm"), `Updated ${timeAgo(a.updated_at)}${a.updated_by_name ? ` by ${a.updated_by_name}` : ""}`)),
      actions));
}
