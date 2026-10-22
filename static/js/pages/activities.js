import { api, errorText } from "../api.js";
import { isLead, state } from "../state.js";
import { activityCard } from "../components/activity-card.js";
import { openActivityForm } from "../components/activity-form.js";
import { STATUS, TYPE, debounce, emptyState, h, icon, select, skeletons } from "../ui.js";

const filters = { search: "", status: "", activity_type: "", period: "all", owner_id: "", follow_up: "", page: 1 };

export async function render(root, ctx) {
  if (state.activityPreset) {                       // e.g. coming from the dashboard or team page
    Object.assign(filters, { search: "", status: "", activity_type: "", period: "all", owner_id: "", follow_up: "", page: 1 }, state.activityPreset);
    state.activityPreset = null;
  }
  // Clear an employee filter that is not available to the current user.
const allowedOwnerIds = new Set(
  state.options.map((person) => String(person.id))
);

if (
  filters.owner_id &&
  !allowedOwnerIds.has(String(filters.owner_id))
) {
  filters.owner_id = "";
}

  const search = h("input", { class: "input", type: "search", placeholder: "Search restaurant or customer", "aria-label": "Search", value: filters.search });
  const status = select("flt-status", [["", "Any status"], ...Object.entries(STATUS)], filters.status);
  const type = select("flt-type", [["", "Any type"], ...Object.entries(TYPE)], filters.activity_type);
  const period = select("flt-period", [["all", "All dates"], ["today", "Today"], ["week", "This week"], ["month", "This month"]], filters.period);
  const follow = select("flt-follow", [["", "Any follow-up"], ["overdue", "Overdue"], ["due_today", "Due today"], ["upcoming", "Upcoming"]], filters.follow_up);
  const owner = isLead()
    ? select("flt-owner", [["", state.user.role === "admin" ? "Everyone" : "Whole team"], ...state.options.map((p) => [p.id, p.id === state.user.id ? `${p.full_name} (you)` : p.full_name])], filters.owner_id)
    : null;
  [status, type, period, follow, owner].forEach((el) => el && el.setAttribute("aria-label", el.id.replace("flt-", "Filter by ")));

  const list = h("div", { class: "list" }, skeletons(3));
  const pager = h("div", { class: "pager" });
  const count = h("p", { class: "muted small" });

  async function load() {
    list.replaceChildren(...skeletons(3));
    try {
      const params = { ...filters, page_size: 10 };
      const data = await api("/api/activities", { params });
      count.textContent = `${data.total} ${data.total === 1 ? "activity" : "activities"}`;
      list.replaceChildren(...(data.items.length
        ? data.items.map((a) => activityCard(a, load))
        : [emptyState("No activities found", Object.values(filters).some((v) => v && v !== "all" && v !== 1) ? "Try clearing some filters." : "Tap “Add activity” to log your first one.")]));
      pager.replaceChildren(
        h("button", { class: "btn sm", type: "button", text: "← Previous", disabled: data.page <= 1, on: { click: () => { filters.page -= 1; load(); window.scrollTo(0, 0); } } }),
        h("span", { class: "small muted", text: `Page ${data.page} of ${data.pages}` }),
        h("button", { class: "btn sm", type: "button", text: "Next →", disabled: data.page >= data.pages, on: { click: () => { filters.page += 1; load(); window.scrollTo(0, 0); } } }));
    } catch (error) {
      list.replaceChildren(h("div", { class: "card" }, h("p", { class: "error-text", text: errorText(error) })));
      pager.replaceChildren();
    }
  }

  const apply = () => { filters.page = 1; load(); };
  search.addEventListener("input", debounce(() => { filters.search = search.value.trim(); apply(); }));
  const bind = (el, key) => el && el.addEventListener("change", () => { filters[key] = el.value; apply(); });
  bind(status, "status"); bind(type, "activity_type"); bind(period, "period"); bind(follow, "follow_up"); bind(owner, "owner_id");

  root.replaceChildren(h("div", { class: "page" },
    h("div", { class: "page-head" },
      h("div", {}, h("h2", { text: "Activities" }), count),
      h("button", { class: "btn primary", type: "button", on: { click: async () => { if (await openActivityForm()) load(); } } }, icon("plus"), "Add activity")),
    h("div", { class: "toolbar" }, h("div", { class: "search input-icon" }, icon("search"), search), status, type, period, follow, owner),
    list, pager));
  load();
}
