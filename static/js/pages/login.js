import { api, errorText, ApiError } from "../api.js";
import { state } from "../state.js";
import { field, h, icon } from "../ui.js";

export function renderLogin(root, { onLoggedIn, notice }) {
  const email = h("input", { id: "login-email", class: "input", type: "email", autocomplete: "username", required: true, placeholder: "you@company.com" });
  const password = h("input", { id: "login-password", class: "input", type: "password", autocomplete: "current-password", required: true });
  const error = h("div", { class: "form-error", hidden: true, role: "alert" });
  const submit = h("button", { class: "btn primary block", type: "submit", text: "Log in" });
  const infoBox = notice ? h("div", { class: "callout" }, icon("alert"), h("span", { text: notice })) : null;

  const form = h("form", { class: "stack", novalidate: true }, infoBox, error,
    field("Email", email), field("Password", password), submit);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;
    if (!email.value.trim() || !password.value) { error.hidden = false; error.textContent = "Enter your email and password."; return; }
    submit.disabled = true; submit.textContent = "Logging in…";
    try {
      const user = await api("/api/auth/login", { method: "POST", body: { email: email.value.trim(), password: password.value } });
      onLoggedIn(user);
    } catch (e) {
      error.hidden = false;
      error.textContent = e instanceof ApiError && e.status === 429 && e.retryAfter
        ? `${errorText(e)} (Retry in about ${Math.ceil(Number(e.retryAfter) / 60)} min.)` : errorText(e);
      password.value = ""; password.focus();
      submit.disabled = false; submit.textContent = "Log in";
    }
  });

  const demo = state.config.demo_accounts || [];
  const demoBox = demo.length ? h("div", { class: "demo-box" },
    h("div", { class: "small strong", text: "Demo accounts" }),
    demo.map((a) => h("button", { class: "demo-btn", type: "button", on: { click: () => { email.value = a.email; password.value = a.password; password.focus(); } } },
      h("span", {}, h("span", { class: "strong", text: a.role[0].toUpperCase() + a.role.slice(1) }), h("span", { class: "tiny muted", text: ` · ${a.email}` })),
      h("span", { class: "tiny", text: "Fill in" })))) : null;

  root.replaceChildren(h("div", { class: "login" }, h("div", { class: "card login-card" },
    h("div", { class: "brand" }, h("div", { class: "brand-mark" }, icon("chart", "lg")), h("span", { text: "FreeBees Sales CRM" })),
    h("div", {}, h("h1", { text: "Welcome back" }), h("p", { class: "muted", text: "Log in to record and track your sales activities." })),
    form, demoBox)));
  email.focus();
}
