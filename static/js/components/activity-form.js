import { api, errorText, fieldErrors } from "../api.js";
import { isAdmin, state } from "../state.js";
import { PRODUCT, TYPE, appToday, field, h, openDialog, select, toast } from "../ui.js";

/** Add (no activity given) or edit an activity. Resolves true if something was saved. */
export function openActivityForm(activity = null) {
  return new Promise((resolve) => {
    const editing = Boolean(activity);
    const today = appToday();
    let saved = false;

    const name = h("input", { id: "f-name", class: "input", maxlength: 120, autocomplete: "off", required: true, value: activity?.customer_name || "" });
    const type = select("f-type", Object.entries(TYPE), activity?.activity_type || "visit");
    const product = select("f-product", [["", "Not specified"], ...Object.entries(PRODUCT).filter(([k]) => k !== "none")], activity?.product_interested || "");
    const start = h("input", { id: "f-start", class: "input", type: "date", max: today, value: activity?.start_date || today });
    const contact = h("input", { id: "f-contact", class: "input", type: "tel", maxlength: 20, placeholder: "e.g. 98765 43210", value: activity?.contact || "" });
    const location = h("input", { id: "f-location", class: "input", maxlength: 120, value: activity?.location || "" });
    const notes = h("textarea", { id: "f-notes", class: "input", maxlength: 500, placeholder: "What happened? What did they say?" }, activity?.notes || "");
    const followDate = h("input", { id: "f-fdate", class: "input", type: "date", value: activity?.follow_up_date || "" });
    const followNotes = h("input", { id: "f-fnotes", class: "input", maxlength: 500, placeholder: "e.g. Call back with pricing", value: activity?.follow_up_notes || "" });

    const fields = {
      customer_name: field("Restaurant / customer", name),
      activity_type: field("Activity type", type),
      product_interested: field("Product interested in", product),
      start_date: field("Start date", start, { hint: "The day you did it. You can backdate if you're logging late." }),
      contact: field("Contact number", contact),
      location: field("Location", location),
      notes: field("Notes", notes),
      follow_up_date: field("Follow-up date", followDate),
      follow_up_notes: field("Follow-up details", followNotes),
    };

    let owner = null, endDate = null;
    if (isAdmin()) {
      const people = state.options.filter((p) => p.role !== "admin" || p.id === state.user.id);
      owner = select("f-owner", people.map((p) => [p.id, p.full_name]), activity?.owner.id || state.user.id);
      fields.owner_id = field("Salesperson", owner, { hint: "Admins can log or reassign activities for anyone." });
    }
    if (activity?.permissions.can_set_end_date) {
      endDate = h("input", { id: "f-end", class: "input", type: "date", max: today, min: activity.start_date, value: activity.end_date || "" });
      fields.end_date = field("End date", endDate, { hint: "When it was completed." });
    }

    const formError = h("div", { class: "form-error", hidden: true, role: "alert" });
    const form = h("form", { class: "form-grid two", novalidate: true },
      formError,
      fields.customer_name && Object.assign(fields.customer_name, {}), fields.activity_type, fields.product_interested,
      fields.start_date, fields.contact, fields.location, owner && fields.owner_id, endDate && fields.end_date,
      Object.assign(fields.notes, { className: "field span-2" }),
      fields.follow_up_date, fields.follow_up_notes,
      !editing && h("p", { class: "hint span-2", text: "New activities start as Pending. A manager or admin moves them forward." }));
    fields.customer_name.classList.add("span-2");

    const submit = h("button", { class: "btn primary", type: "submit", text: editing ? "Save changes" : "Save activity" });
    const cancel = h("button", { class: "btn", type: "button", text: "Cancel" });
    const showError = (text) => { formError.hidden = !text; formError.textContent = text || ""; };

    const dialogHandle = openDialog({
      title: editing ? "Edit activity" : "Add activity",
      body: h("div", {}, form),
      footer: [cancel, submit],
    });
    dialogHandle.dialog.addEventListener("close", () => resolve(saved));
    cancel.addEventListener("click", dialogHandle.close);
    submit.addEventListener("click", () => form.requestSubmit());
    name.focus();

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      showError("");
      Object.values(fields).forEach((f) => f.setError(""));

      const problems = {};
      if (name.value.trim().length < 2) problems.customer_name = "Enter at least 2 characters.";
      if (!start.value) problems.start_date = "Pick the start date.";
      else if (start.value > today) problems.start_date = "Start date can't be in the future.";
      if (followDate.value && start.value && followDate.value < start.value) problems.follow_up_date = "Can't be before the start date.";
      if (contact.value && !/^[0-9+\-\s()]{7,20}$/.test(contact.value.trim())) problems.contact = "Enter a valid phone number.";
      if (endDate?.value && endDate.value < start.value) problems.end_date = "Can't be before the start date.";
      if (Object.keys(problems).length) {
        for (const [key, message] of Object.entries(problems)) fields[key].setError(message);
        return;
      }

      const payload = {
        customer_name: name.value.trim(), activity_type: type.value, product_interested: product.value || null,
        start_date: start.value, contact: contact.value.trim() || null, location: location.value.trim() || null,
        notes: notes.value.trim() || null, follow_up_date: followDate.value || null, follow_up_notes: followNotes.value.trim() || null,
      };
      if (owner) payload.owner_id = owner.value;
      if (endDate) payload.end_date = endDate.value || null;

      submit.disabled = true; submit.textContent = "Saving…";
      try {
        await api(editing ? `/api/activities/${activity.id}` : "/api/activities", { method: editing ? "PATCH" : "POST", body: payload });
        saved = true;
        toast(editing ? "Activity updated" : "Activity saved");
        dialogHandle.close();
      } catch (error) {
        const byField = fieldErrors(error);
        const known = Object.keys(byField).filter((k) => fields[k]);
        known.forEach((k) => fields[k].setError(byField[k]));
        showError(known.length ? "Please fix the highlighted fields." : errorText(error));   // 409 duplicates, 429, 403 …
        submit.disabled = false; submit.textContent = editing ? "Save changes" : "Save activity";
      }
    });
  });
}
