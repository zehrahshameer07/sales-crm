import { api, errorText } from "../api.js";
import { STATUS, appToday, field, fullDateTime, h, openDialog, statusBadge, toast } from "../ui.js";

/** Move an activity forward. Completing asks for the end date. Resolves true when changed. */
export function changeStatus(activity, newStatus) {
  return new Promise((resolve) => {
    let done = false;
    const send = async (body, handle, button) => {
      if (button) { button.disabled = true; button.textContent = "Saving…"; }
      try {
        await api(`/api/activities/${activity.id}/status`, { method: "POST", body });
        done = true;
        toast(`Marked ${STATUS[newStatus].toLowerCase()}`);
        handle?.close();
        resolve(true);
      } catch (error) {
        toast(errorText(error), "error");
        if (button) { button.disabled = false; button.textContent = "Mark completed"; }
      }
    };

    if (newStatus !== "completed") { send({ status: newStatus }); return; }

    const today = appToday();
    const end = h("input", { id: "s-end", class: "input", type: "date", min: activity.start_date, max: today, value: today });
    const wrap = field("When was it completed?", end, { hint: "Defaults to today. Use an earlier day if it was finished before." });
    const confirm = h("button", { class: "btn primary", type: "button", text: "Mark completed" });
    const handle = openDialog({
      title: `Complete “${activity.customer_name}”`,
      body: h("div", { class: "stack" },
        h("p", { class: "muted", text: "Completed activities are locked. Only an admin can edit them afterwards." }), wrap),
      footer: [h("button", { class: "btn", type: "button", text: "Cancel", on: { click: () => handle.close() } }), confirm],
    });
    handle.dialog.addEventListener("close", () => { if (!done) resolve(false); });
    confirm.addEventListener("click", () => {
      if (!end.value || end.value < activity.start_date || end.value > today) { wrap.setError("Pick a day between the start date and today."); return; }
      send({ status: "completed", end_date: end.value }, handle, confirm);
    });
  });
}

export async function showHistory(activity) {
  const body = h("div", { class: "timeline" }, h("p", { class: "muted", text: "Loading…" }));
  openDialog({ title: `History — ${activity.customer_name}`, body });
  try {
    const rows = await api(`/api/activities/${activity.id}/history`);
    body.replaceChildren(...rows.map((row) => h("div", { class: "tl" },
      h("span", { class: "dot" }),
      h("div", {},
        h("div", { class: "row wrap", style: { gap: "6px" } },
          row.from_status ? [statusBadge(row.from_status), h("span", { class: "muted", text: "→" })] : h("span", { class: "muted small", text: "Logged as" }),
          statusBadge(row.to_status)),
        h("div", { class: "small muted", text: `${row.changed_by_name || "Unknown"} · ${fullDateTime(row.changed_at)}` })))));
  } catch (error) {
    body.replaceChildren(h("p", { class: "error-text", text: errorText(error) }));
  }
}
