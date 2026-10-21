// Dashboard. Same page, different content by role:
//  salesperson -> personal numbers | manager -> team numbers + per-employee table | admin -> whole company
import { api, errorText } from "../api.js";
import { isAdmin, isLead, state } from "../state.js";
import { activityCard } from "../components/activity-card.js";
import { openActivityForm } from "../components/activity-form.js";
import { PRODUCT, TYPE, avatar, card, emptyState, formatDays, h, hbars, icon, percentBar, ring, roleBadge, skeletons, trend } from "../ui.js";

let period = "month";
const PERIODS = [["today", "Today"], ["week", "This week"], ["month", "This month"], ["all", "All time"]];

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

export async function render(root, ctx) {
  const user = state.user;
  const body = h("div", { class: "stack" }, skeletons(2, 120));
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Period" }, PERIODS.map(([value, label]) =>
    h("button", { type: "button", "aria-pressed": String(value === period), text: label, on: { click: () => { period = value; render(root, ctx); } } })));
  const subtitle = h("p", { text: "Loading…" });

  root.replaceChildren(h("div", { class: "page" },
    h("div", { class: "page-head" },
      h("div", {}, h("h2", { text: `${greeting()}, ${user.full_name.split(" ")[0]}` }), subtitle),
      h("div", { class: "row wrap" }, seg,
        h("button", { class: "btn primary", type: "button", on: { click: async () => { if (await openActivityForm()) render(root, ctx); } } }, icon("plus"), "Add activity"))),
    body));

  try {
    const [ov, recent, overdue, dueToday, team] = await Promise.all([
      api("/api/stats/overview", { params: { period } }),
      api("/api/activities", { params: { period, page_size: 5 } }),
      api("/api/activities", { params: { follow_up: "overdue", page_size: 4 } }),
      api("/api/activities", { params: { follow_up: "due_today", page_size: 4 } }),
      isLead() ? api("/api/stats/team", { params: { period } }) : Promise.resolve([]),
    ]);
    subtitle.textContent = user.role === "salesperson" ? "Here's how your work is going."
      : `${ov.scope_label} · ${ov.scope_people} ${ov.scope_people === 1 ? "person" : "people"}`;

    const kpi = (label, value, ico, tone) => h("div", { class: "card kpi" },
      h("div", { class: `ico ${tone}` }, icon(ico, "lg")), h("div", {}, h("div", { class: "num", text: String(value) }), h("div", { class: "lbl", text: label })));

    const d = ov.durations;
    const timeCard = card("Time to complete", h("div", {},
      d.avg_days_to_complete === null
        ? h("p", { class: "muted", text: "Complete an activity to see how fast deals close." })
        : [h("div", { class: "big" }, String(d.avg_days_to_complete), h("small", { text: ` days on average` })),
           h("div", { class: "mini-stats" },
             h("div", {}, h("strong", { text: formatDays(d.fastest_days) }), h("span", { text: "Fastest" })),
             h("div", {}, h("strong", { text: formatDays(d.slowest_days) }), h("span", { text: "Slowest" })),
             h("div", {}, h("strong", { text: String(d.timed_count) }), h("span", { text: "Measured" })))]));

    const f = ov.follow_ups;
    const followItems = [...overdue.items, ...dueToday.items].slice(0, 4);
    const followCard = card("Follow-ups", h("div", { class: "stack", style: { gap: "10px" } },
      h("div", { class: "row wrap" },
        h("span", { class: `chip ${f.overdue ? "bad" : ""}`, text: `${f.overdue} overdue` }),
        h("span", { class: `chip ${f.due_today ? "warn" : ""}`, text: `${f.due_today} today` }),
        h("span", { class: "chip", text: `${f.next_7_days} next 7 days` })),
      followItems.length
        ? followItems.map((a) => h("div", { class: "row between small" },
            h("span", { class: "ellipsis", text: `${a.customer_name}${isLead() ? ` · ${a.owner.full_name.split(" ")[0]}` : ""}` }),
            h("span", { class: "muted ellipsis", text: a.follow_up_notes || "" })))
        : h("p", { class: "muted small", text: "Nothing needs chasing right now. 🎉" }),
      (f.overdue || f.due_today) && h("button", { class: "btn sm", type: "button", on: { click: () => { state.activityPreset = { follow_up: f.overdue ? "overdue" : "due_today", period: "all" }; ctx.navigate("activities"); } } }, "View follow-ups")));

    const sections = [
      h("div", { class: "grid cols-4" },
        kpi("Activities", ov.total, "list", "brand"), kpi("Pending", ov.pending, "clock", "warn"),
        kpi("In progress", ov.in_progress, "chart", "info"), kpi("Completed", ov.completed, "check", "ok")),
      h("div", { class: "grid cols-3" },
        card("Completion", h("div", { class: "row", style: { gap: "18px" } }, ring(ov.completion_rate),
          h("p", { class: "muted small", text: `${ov.completed} of ${ov.total} activities completed in this period.` }))),
        timeCard, followCard),
    ];

    if (isLead()) sections.push(...teamSections(team, ctx));

    sections.push(
      h("div", { class: "grid cols-main" },
        card("Activity in the last 7 days", trend(ov.last_7_days), h("span", { class: "tiny muted", text: "by start date" })),
        card("By activity type", hbars(ov.by_type, TYPE))),
      h("div", { class: "grid cols-2" },
        card("By product", hbars(ov.by_product.filter((p) => p.count || p.key !== "none"), PRODUCT)),
        card(user.role === "salesperson" ? "Recent activity" : "Recent activity in scope",
          recent.items.length
            ? h("div", { class: "list" }, recent.items.map((a) => activityCard(a, () => render(root, ctx))))
            : emptyState("No activities in this period", "Try a wider period, or add one.",
                h("button", { class: "btn primary sm", type: "button", on: { click: async () => { if (await openActivityForm()) render(root, ctx); } } }, icon("plus", "sm"), "Add activity"))),
      ));
    body.replaceChildren(...sections);
  } catch (error) {
    body.replaceChildren(h("div", { class: "card" }, h("p", { class: "error-text", text: errorText(error) })));
  }
}

function goTo(ctx, personId) {
  state.activityPreset = { owner_id: personId, period };
  ctx.navigate("activities");
}

function teamSections(team, ctx) {
  const out = [];
  const cols = "minmax(0,2fr) 100px minmax(0,1.5fr) 90px 90px";
  const rows = team.filter((r) => r.total > 0 || r.role === "salesperson");
  const table = h("div", { class: "table", style: { "--cols": cols } },
    h("div", { class: "th" }, h("span", { text: "Employee" }), h("span", { class: "num", text: "Activities" }), h("span", { text: "Completion" }), h("span", { class: "num", text: "Avg days" }), h("span", { class: "num", text: "Overdue" })),
    rows.length ? rows.map((r) => h("div", { class: "tr clickable", tabindex: "0", role: "button", "aria-label": `View ${r.full_name}'s activities`,
      on: { click: () => goTo(ctx, r.user_id), keydown: (e) => { if (e.key === "Enter") goTo(ctx, r.user_id); } } },
      h("div", { class: "td name cell-person" }, avatar(r.full_name),
        h("div", {}, h("div", { class: "strong ellipsis", text: r.is_self ? `${r.full_name} (you)` : r.full_name }),
          h("div", { class: "tiny muted ellipsis", text: [r.role === "manager" ? "Manager" : "Salesperson", r.region].filter(Boolean).join(" · ") }))),
      h("div", { class: "td num", "data-label": "Activities", text: String(r.total) }),
      h("div", { class: "td", "data-label": "Completion" }, percentBar(r.completion_rate)),
      h("div", { class: "td num", "data-label": "Avg days", text: r.avg_days_to_complete === null ? "–" : String(r.avg_days_to_complete) }),
      h("div", { class: "td num", "data-label": "Overdue" }, r.follow_ups_overdue ? h("span", { class: "chip bad", text: String(r.follow_ups_overdue) }) : h("span", { class: "muted", text: "0" }))))
      : emptyState("No team members yet", "People who report to you will appear here."));
  out.push(card(isAdmin() ? "Everyone's progress" : "Your team's progress", table, h("span", { class: "tiny muted", text: "Click a person to see their activities" })));

  const ranked = team.filter((r) => r.completed > 0).slice(0, 3);
  const extra = [];
  if (ranked.length) {
    extra.push(card("Top performers", h("div", { class: "stack", style: { gap: "12px" } }, ranked.map((r, i) =>
      h("div", { class: "row" }, h("span", { class: `badge plain ${i === 0 ? "in_progress" : ""}`, text: `#${i + 1}` }), avatar(r.full_name, "sm"),
        h("span", { class: "grow ellipsis strong", text: r.full_name }), h("span", { class: "small muted", text: `${r.completed} completed` }))))));
  }
  if (isAdmin()) {
    const managers = team.filter((r) => r.role === "manager");
    const cards = managers.map((m) => {
      const members = team.filter((r) => r.manager_id === m.user_id || r.user_id === m.user_id);
      const total = members.reduce((s, r) => s + r.total, 0), done = members.reduce((s, r) => s + r.completed, 0);
      return h("div", { class: "row" }, avatar(m.full_name, "sm"),
        h("div", { class: "grow" }, h("div", { class: "strong", text: `${m.full_name}'s team` }), h("div", { class: "tiny muted", text: `${members.length} ${members.length === 1 ? "person" : "people"} · ${total} activities` })),
        h("div", { style: { width: "110px" } }, percentBar(total ? Math.round((done * 100) / total) : 0)));
    });
    if (cards.length) extra.push(card("Teams", h("div", { class: "stack" }, cards)));
  }
  if (extra.length) out.push(h("div", { class: `grid ${extra.length > 1 ? "cols-2" : ""}` }, extra));
  return out;
}
