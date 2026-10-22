// App shell: login gate, role-based navigation, user menu and routing.
import { api, errorText, setUnauthorizedHandler } from "./api.js";
import { isAdmin, isLead, state } from "./state.js";
import { openActivityForm } from "./components/activity-form.js";
import { avatar, field, h, icon, openDialog, roleBadge, toast } from "./ui.js";
import { renderLogin } from "./pages/login.js";
const THEME_KEY = "freebees-theme";

function applyTheme(theme) {
  if (theme === "light" || theme === "dark") {
    document.documentElement.dataset.theme = theme;
  } else {
    delete document.documentElement.dataset.theme;
  }
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light");

  const next = current === "dark" ? "light" : "dark";

  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
}

applyTheme(localStorage.getItem(THEME_KEY) || "system");
const root = document.getElementById("root");
const PAGES = {
  dashboard: { title: "Dashboard", icon: "home", load: () => import("./pages/dashboard.js") },
  activities: { title: "Activities", icon: "list", load: () => import("./pages/activities.js") },
  team: { title: "Team", icon: "users", load: () => import("./pages/team.js"), allow: isLead },
  reports: { title: "Reports", icon: "file", load: () => import("./pages/reports.js") },
  users: { title: "Employees", icon: "shield", load: () => import("./pages/users.js"), allow: isAdmin },
};
const allowed = () => Object.entries(PAGES).filter(([, p]) => !p.allow || p.allow());

let view, titleEl, current = "dashboard";

function showLogin(notice) {
  state.user = null; state.options = [];
  renderLogin(root, { notice, onLoggedIn: (user) => { state.user = user; start(); } });
}
setUnauthorizedHandler(() => { if (state.user) showLogin("Your session has expired. Please log in again."); });

async function logout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* cookie is cleared server-side anyway */ }
  window.location.hash = "";
  showLogin();
}

function changePasswordDialog({ forced = false } = {}) {
  return new Promise((resolve) => {
    const current = h("input", { id: "cp-current", class: "input", type: "password", autocomplete: "current-password" });
    const next = h("input", { id: "cp-new", class: "input", type: "password", autocomplete: "new-password" });
    const again = h("input", { id: "cp-again", class: "input", type: "password", autocomplete: "new-password" });
    const w = {
      current: field(
  forced ? "Temporary password" : "Current password",
  current,
  {
    hint: forced
      ? "Enter the temporary password provided by your administrator."
      : "Enter the password you currently use to sign in. If you have forgotten it, contact an administrator for a reset."
  }
),
      next: field("New password", next, { hint: `At least ${state.config.password_min_length || 10} characters with letters and numbers.` }),
      again: field("Repeat new password", again),
    };
    const error = h("div", { class: "form-error", hidden: true, role: "alert" });
    const form = h("form", { class: "stack", novalidate: true }, forced && h("div", { class: "callout warn" }, icon("lock"), h("span", { text: "For your security, choose a new password before you continue." })), error, w.current, w.next, w.again);
    const submit = h("button", { class: "btn primary", type: "submit", text: "Change password" });
    let done = false;
    const handle = openDialog({
      title: "Change password", body: form, dismissible: !forced,
      footer: [!forced && h("button", { class: "btn", type: "button", text: "Cancel", on: { click: () => handle.close() } }), submit].filter(Boolean),
    });
    handle.dialog.addEventListener("close", () => resolve(done));
    submit.addEventListener("click", () => form.requestSubmit());
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      error.hidden = true; Object.values(w).forEach((x) => x.setError(""));
      if (!current.value) { w.current.setError("Enter your current password."); return; }
      if (next.value !== again.value) { w.again.setError("The passwords don't match."); return; }
      submit.disabled = true;
      try {
        state.user = await api("/api/auth/change-password", { method: "POST", body: { current_password: current.value, new_password: next.value } });
        done = true; toast("Password changed"); handle.close();
      } catch (e) { error.hidden = false; error.textContent = errorText(e); submit.disabled = false; }
    });
    current.focus();
  });
}

function userMenu() {
  const u = state.user;
  const panel = h("div", { class: "menu", hidden: true, role: "menu" },
    h("div", { class: "row" }, avatar(u.full_name, "lg"), h("div", { class: "grow", style: { minWidth: 0 } }, h("div", { class: "strong ellipsis", text: u.full_name }), roleBadge(u.role))),
    h("dl", { class: "kv" },
      h("dt", { text: "Email" }), h("dd", { text: u.email }),
      u.phone && [h("dt", { text: "Phone" }), h("dd", { text: u.phone })],
      u.designation && [h("dt", { text: "Designation" }), h("dd", { text: u.designation })],
      u.region && [h("dt", { text: "Region" }), h("dd", { text: u.region })],
      u.manager_name && [h("dt", { text: "Reports to" }), h("dd", { text: u.manager_name })]),
    h("hr"),
    h("button", {
  class: "menu-item",
  type: "button",
  role: "menuitem",
  on: {
    click: () => {
      toggleTheme();
      panel.hidden = true;
    }
  }
}, icon("sun"), "Toggle light / dark mode"),
    h("button", { class: "menu-item", type: "button", role: "menuitem", on: { click: () => { panel.hidden = true; changePasswordDialog(); } } }, icon("key"), "Change password"),
    h("button", { class: "menu-item", type: "button", role: "menuitem", on: { click: logout } }, icon("logout"), "Log out"));
  const button = h("button", { class: "btn icon-only", type: "button", "aria-label": "Account menu", "aria-haspopup": "true", "aria-expanded": "false",
    on: { click: (e) => { e.stopPropagation(); panel.hidden = !panel.hidden; button.setAttribute("aria-expanded", String(!panel.hidden)); } } }, avatar(u.full_name, "sm"));
  document.addEventListener("click", (e) => { if (!panel.contains(e.target)) { panel.hidden = true; button.setAttribute("aria-expanded", "false"); } });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") panel.hidden = true; });
  panel.addEventListener("click", (e) => e.stopPropagation());
  return h("div", { class: "menu-wrap" }, button, panel);
}

function buildShell() {
  const u = state.user;
  const links = (cls) => allowed().map(([key, p]) => h("a", { class: cls, href: `#/${key}`, data: { route: key }, "aria-label": p.title }, icon(p.icon), cls === "tab" ? h("span", { text: p.title }) : p.title));
  titleEl = h("h1", { text: "" });
  view = h("main", { id: "view", tabindex: "-1" });
  const shell = h("div", { class: "shell" },
    h("aside", { class: "sidebar" },
      h("div", { class: "brand" }, h("div", { class: "brand-mark" }, icon("chart", "lg")), h("span", { text: "FreeBees CRM" })),
      h("nav", { class: "nav", "aria-label": "Main" }, links("")),
      h("div", { class: "sidebar-foot" },
        h("div", { class: "me" }, avatar(u.full_name), h("div", { style: { minWidth: 0 } }, h("div", { class: "strong ellipsis", text: u.full_name }), roleBadge(u.role))))),
    h("div", { class: "content" },
      h("header", { class: "topbar" }, h("div", { class: "brand brand-top" }, h("div", { class: "brand-mark" }, icon("chart"))), titleEl, userMenu()),
      view),
    h("nav", { class: "tabbar", "aria-label": "Main" }, links("tab")),
    h("button", { class: "fab", type: "button", "aria-label": "Add activity", on: { click: async () => { if (await openActivityForm()) route(); } } }, icon("plus")));
  root.replaceChildren(shell);
}

function setActive(key) {
  document.querySelectorAll("[data-route]").forEach((a) => {
    const on = a.dataset.route === key;
    a.classList.toggle("active", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
}

const ctx = { navigate: (key) => { window.location.hash = `#/${key}`; } };

async function route() {
  let key = window.location.hash.replace(/^#\/?/, "") || "dashboard";
  if (!PAGES[key] || (PAGES[key].allow && !PAGES[key].allow())) key = "dashboard";
  current = key;
  titleEl.textContent = PAGES[key].title;
  document.title = `${PAGES[key].title} · FreeBees Sales CRM`;
  setActive(key);
  try {
    const page = await PAGES[key].load();
    if (current === key) await page.render(view, ctx);
  } catch (error) {
    view.replaceChildren(h("div", { class: "page" }, h("div", { class: "card" }, h("p", { class: "error-text", text: "This page failed to load. Please refresh." }))));
    console.error(error);
  }
  window.scrollTo(0, 0);
}

async function loadOptions() { state.options = await api("/api/users/options"); }

async function start() {
  if (state.user.must_change_password) {
    root.replaceChildren(h("div", { class: "login" }));
    await changePasswordDialog({ forced: true });
  }
  try { await loadOptions(); } catch (error) { showLogin(errorText(error)); return; }
  buildShell();
  window.removeEventListener("hashchange", route);
  window.addEventListener("hashchange", route);
  route();
}

(async function boot() {
  try { state.config = await api("/api/auth/config"); } catch { /* defaults are fine */ }
  try { state.user = await api("/api/auth/me"); await start(); } catch { showLogin(); }
})();
