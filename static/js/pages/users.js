// Admin only: manage employees (create, edit, deactivate, reset password, unlock).
import { api, errorText, fieldErrors } from "../api.js";
import { state } from "../state.js";
import { ROLE, avatar, confirmDialog, copyText, debounce, emptyState, field, h, icon, openDialog, roleBadge, select, skeletons, timeAgo, toast } from "../ui.js";

const filters = { search: "", role: "", is_active: "", page: 1 };

function secretDialog(title, intro, secret) {
  openDialog({
    title,
    body: h("div", { class: "stack" },
      h("p", { text: intro }), h("div", { class: "secret", text: secret }),
      h("div", { class: "callout warn" }, icon("alert"), h("span", { text: "This is shown only once. Share it securely. They will be asked to choose their own password at first login." }))),
    footer: [h("button", { class: "btn primary", type: "button", text: "Copy password", on: { click: () => copyText(secret) } })],
  });
}

async function openUserForm(user, managers) {
  return new Promise((resolve) => {
    const editing = Boolean(user);
    let saved = false;
    const f = {
      full_name: h("input", { id: "u-name", class: "input", maxlength: 120, value: user?.full_name || "" }),
      email: h("input", { id: "u-email", class: "input", type: "email", maxlength: 254, value: user?.email || "" }),
      phone: h("input", { id: "u-phone", class: "input", type: "tel", maxlength: 20, value: user?.phone || "" }),
      role: select("u-role", Object.entries(ROLE), user?.role || "salesperson"),
      manager_id: select("u-manager", [["", "No manager"], ...managers.map((m) => [m.id, `${m.full_name} (${ROLE[m.role]})`])], user?.manager_id || ""),
      designation: h("input", { id: "u-desig", class: "input", maxlength: 80, value: user?.designation || "" }),
      region: h("input", { id: "u-region", class: "input", maxlength: 80, value: user?.region || "" }),
      employee_code: h("input", { id: "u-code", class: "input", maxlength: 30, value: user?.employee_code || "" }),
    };
    const wraps = {
      full_name: field("Full name", f.full_name), email: field("Email (used to log in)", f.email), phone: field("Phone", f.phone),
      role: field("Role", f.role), manager_id: field("Reports to", f.manager_id, { hint: "Managers see and approve their team's work." }),
      designation: field("Designation", f.designation), region: field("Region / area", f.region),
      employee_code: field("Employee code", f.employee_code, { hint: "Optional. Must be unique." }),
    };
    let password = null;
    if (!editing) {
      password = h("input", { id: "u-pass", class: "input", type: "text", autocomplete: "off", placeholder: "Leave empty to generate one" });
      wraps.password = field("Initial password", password, { hint: "They must change it at first login." });
    }
    const syncManager = () => { wraps.manager_id.hidden = f.role.value === "admin"; };
    f.role.addEventListener("change", syncManager); syncManager();

    const error = h("div", { class: "form-error", hidden: true, role: "alert" });
    const form = h("form", { class: "form-grid two", novalidate: true }, error, Object.values(wraps));
    const submit = h("button", { class: "btn primary", type: "submit", text: editing ? "Save changes" : "Create user" });
    const handle = openDialog({ title: editing ? `Edit ${user.full_name}` : "Add employee", body: form,
      footer: [h("button", { class: "btn", type: "button", text: "Cancel", on: { click: () => handle.close() } }), submit] });
    handle.dialog.addEventListener("close", () => resolve(saved));
    submit.addEventListener("click", () => form.requestSubmit());

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      error.hidden = true; Object.values(wraps).forEach((w) => w.setError(""));
      if (f.full_name.value.trim().length < 2) { wraps.full_name.setError("Enter at least 2 characters."); return; }
      if (!/^\S+@\S+\.\S+$/.test(f.email.value.trim())) { wraps.email.setError("Enter a valid email."); return; }
      const payload = {
        full_name: f.full_name.value.trim(), email: f.email.value.trim(), phone: f.phone.value.trim() || null, role: f.role.value,
        manager_id: f.role.value === "admin" ? null : f.manager_id.value || null, designation: f.designation.value.trim() || null,
        region: f.region.value.trim() || null, employee_code: f.employee_code.value.trim() || null,
      };
      if (password) payload.password = password.value || null;
      submit.disabled = true;
      try {
        const result = await api(editing ? `/api/users/${user.id}` : "/api/users", { method: editing ? "PATCH" : "POST", body: payload });
        saved = true;
        handle.close();
        toast(editing ? "User updated" : "User created");
        if (!editing && result.temporary_password) secretDialog("Temporary password", `Account created for ${result.full_name}. Their temporary password is:`, result.temporary_password);
      } catch (err) {
        const byField = fieldErrors(err);
        const known = Object.keys(byField).filter((k) => wraps[k]);
        known.forEach((k) => wraps[k].setError(byField[k]));
        error.hidden = known.length > 0; error.textContent = known.length ? "" : errorText(err); error.hidden = known.length > 0;
        submit.disabled = false;
      }
    });
  });
}

export async function render(root, ctx) {
  const list = h("div", {}, skeletons(1, 260));
  const pager = h("div", { class: "pager" });
  const search = h("input", { class: "input", type: "search", placeholder: "Search name or email", "aria-label": "Search users", value: filters.search });
  const role = select("flt-role", [["", "All roles"], ...Object.entries(ROLE)], filters.role);
  const active = select("flt-active", [["", "Active & inactive"], ["true", "Active"], ["false", "Deactivated"]], filters.is_active);

  async function managersList() {
    const data = await api("/api/users", { params: { page_size: 100 } });
    return data.items.filter((u) => (u.role === "manager" || u.role === "admin") && u.is_active);
  }
  async function reloadOptions() { state.options = await api("/api/users/options"); }

  async function load() {
    try {
      const data = await api("/api/users", { params: { ...filters, page_size: 10 } });
      const cols = "minmax(0,2fr) 110px minmax(0,1.2fr) minmax(0,1fr) 110px 230px";
      const act = (user) => h("div", { class: "a-actions", style: { marginTop: 0 } },
        h("button", { class: "btn sm", type: "button", on: { click: async () => { if (await openUserForm(user, await managersList())) { await reloadOptions(); load(); } } } }, icon("edit", "sm"), "Edit"),
        h("button", { class: "btn sm", type: "button", title: "Reset password", on: { click: async () => {
          if (!(await confirmDialog({ title: "Reset password?", message: `${user.full_name} will be logged out and must choose a new password.`, confirmText: "Reset" }))) return;
          try { const r = await api(`/api/users/${user.id}/reset-password`, { method: "POST" }); secretDialog("New temporary password", `Password reset for ${user.full_name}:`, r.temporary_password); load(); } catch (e) { toast(errorText(e), "error"); }
        } } }, icon("key", "sm"), "Reset"),
        user.is_locked && h("button", { class: "btn sm", type: "button", on: { click: async () => { try { await api(`/api/users/${user.id}/unlock`, { method: "POST" }); toast("Account unlocked"); load(); } catch (e) { toast(errorText(e), "error"); } } } }, icon("lock", "sm"), "Unlock"),
        h("button", { class: `btn sm ${user.is_active ? "danger" : ""}`, type: "button", on: { click: async () => {
          if (user.is_active && !(await confirmDialog({ title: "Deactivate account?", message: `${user.full_name} won't be able to log in. Their activities and history are kept.`, confirmText: "Deactivate", danger: true }))) return;
          try { await api(`/api/users/${user.id}`, { method: "PATCH", body: { is_active: !user.is_active } }); toast(user.is_active ? "Account deactivated" : "Account reactivated"); await reloadOptions(); load(); } catch (e) { toast(errorText(e), "error"); }
        } } }, user.is_active ? "Deactivate" : "Reactivate"));
      list.replaceChildren(h("section", { class: "card" }, h("div", { class: "table", style: { "--cols": cols } },
        h("div", { class: "th" }, ["Employee", "Role", "Reports to", "Region", "Last login", ""].map((t) => h("span", { text: t }))),
        data.items.length ? data.items.map((u) => h("div", { class: "tr" },
          h("div", { class: "td name cell-person" }, avatar(u.full_name), h("div", {}, h("div", { class: "strong ellipsis", text: u.full_name }), h("div", { class: "tiny muted ellipsis", text: u.email }))),
          h("div", { class: "td", "data-label": "Role" }, h("div", { class: "row wrap", style: { gap: "6px" } }, roleBadge(u.role), !u.is_active && h("span", { class: "badge off", text: "Deactivated" }), u.is_locked && h("span", { class: "badge off", text: "Locked" }))),
          h("div", { class: "td", "data-label": "Reports to", text: u.manager_name || "–" }),
          h("div", { class: "td", "data-label": "Region", text: u.region || "–" }),
          h("div", { class: "td", "data-label": "Last login", text: u.last_login_at ? timeAgo(u.last_login_at) : "Never" }),
          h("div", { class: "td" }, act(u))))
          : emptyState("No users match", "Try changing the filters."))));
      pager.replaceChildren(
        h("button", { class: "btn sm", type: "button", text: "← Previous", disabled: data.page <= 1, on: { click: () => { filters.page -= 1; load(); } } }),
        h("span", { class: "small muted", text: `${data.total} people · page ${data.page} of ${data.pages}` }),
        h("button", { class: "btn sm", type: "button", text: "Next →", disabled: data.page >= data.pages, on: { click: () => { filters.page += 1; load(); } } }));
    } catch (e) { list.replaceChildren(h("div", { class: "card" }, h("p", { class: "error-text", text: errorText(e) }))); }
  }

  const apply = () => { filters.page = 1; load(); };
  search.addEventListener("input", debounce(() => { filters.search = search.value.trim(); apply(); }));
  role.addEventListener("change", () => { filters.role = role.value; apply(); });
  active.addEventListener("change", () => { filters.is_active = active.value; apply(); });

  root.replaceChildren(h("div", { class: "page" },
    h("div", { class: "page-head" }, h("div", {}, h("h2", { text: "Employees" }), h("p", { text: "Create accounts, assign managers and control access." })),
      h("button", { class: "btn primary", type: "button", on: { click: async () => { if (await openUserForm(null, await managersList())) { await reloadOptions(); load(); } } } }, icon("plus"), "Add employee")),
    h("div", { class: "toolbar users" }, h("div", { class: "input-icon" }, icon("search"), search), role, active),
    list, pager));
  load();
}
