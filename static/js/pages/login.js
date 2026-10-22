
import { api, errorText, ApiError } from "../api.js";
import { state } from "../state.js";
import { field, h, icon } from "../ui.js";

export function renderLogin(root, { onLoggedIn, notice }) {
  const email = h("input", {
    id: "login-email",
    class: "input",
    type: "email",
    autocomplete: "username",
    required: true,
    placeholder: "you@company.com"
  });

  const password = h("input", {
    id: "login-password",
    class: "input",
    type: "password",
    autocomplete: "current-password",
    required: true,
    placeholder: "Enter your password"
  });

  const passwordWrap = h("div", { class: "login-password-wrap" },
    password,
    h("button", {
      class: "login-password-toggle",
      type: "button",
      "aria-label": "Show password",
      on: {
        click: (event) => {
          const visible = password.type === "password";
          password.type = visible ? "text" : "password";
          event.currentTarget.setAttribute(
            "aria-label",
            visible ? "Hide password" : "Show password"
          );
          event.currentTarget.textContent = visible ? "Hide" : "Show";
        }
      }
    }, "Show")
  );

  const error = h("div", {
    class: "form-error",
    hidden: true,
    role: "alert"
  });

  const submit = h("button", {
    class: "btn primary block login-submit",
    type: "submit",
    text: "Log in"
  });

  const infoBox = notice
    ? h("div", { class: "callout" }, icon("alert"), h("span", { text: notice }))
    : null;

  const form = h("form", { class: "stack login-form", novalidate: true },
    infoBox,
    error,
    field("Email", email),
    field("Password", passwordWrap),
    submit
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.hidden = true;

    if (!email.value.trim() || !password.value) {
      error.hidden = false;
      error.textContent = "Enter your email and password.";
      return;
    }

    submit.disabled = true;
    submit.textContent = "Signing in…";

    try {
      const user = await api("/api/auth/login", {
        method: "POST",
        body: {
          email: email.value.trim(),
          password: password.value
        }
      });

      onLoggedIn(user);
    } catch (e) {
      error.hidden = false;
      error.textContent =
        e instanceof ApiError && e.status === 429 && e.retryAfter
          ? `${errorText(e)} (Retry in about ${Math.ceil(Number(e.retryAfter) / 60)} min.)`
          : errorText(e);

      password.value = "";
      password.focus();
      submit.disabled = false;
      submit.textContent = "Log in";
    }
  });

  const demo = state.config.demo_accounts || [];

  const demoDetails = demo.length
    ? h("details", { class: "demo-box login-demo" },
        h("summary", { class: "demo-summary" },
          h("span", {},
            h("span", { class: "strong", text: "Quick demo access" }),
            h("span", {
              class: "tiny muted",
              text: "Use a sample account to explore the CRM"
            })
          ),
          h("span", { class: "demo-chevron", "aria-hidden": "true" }, "⌄")
        ),
        h("div", { class: "demo-list" },
          demo.map((a) =>
            h("div", { class: "demo-row" },
              h("div", { class: "demo-account-info" },
                h("span", {
                  class: "strong",
                  text: a.role[0].toUpperCase() + a.role.slice(1)
                }),
                h("span", {
                  class: "tiny muted demo-email",
                  text: a.email
                })
              ),
              h("button", {
                class: "btn demo-use",
                type: "button",
                text: "Use",
                on: {
                  click: () => {
                    email.value = a.email;
                    password.value = a.password;
                    password.type = "password";
                    passwordWrap.querySelector("button").textContent = "Show";
                    passwordWrap.querySelector("button").setAttribute(
                      "aria-label",
                      "Show password"
                    );
                    error.hidden = true;
                    password.focus();
                  }
                }
              })
            )
          )
        )
      )
    : null;

  root.replaceChildren(
    h("div", { class: "login login-modern" },
      h("div", { class: "card login-card login-card-modern" },
        h("div", { class: "login-brand" },
          h("div", { class: "brand-mark" }, icon("chart", "lg")),
          h("div", {},
            h("div", { class: "login-brand-name", text: "FreeBees" }),
            h("div", { class: "login-brand-subtitle", text: "SALES CRM" })
          )
        ),
        h("div", { class: "login-heading" },
          h("div", { class: "login-eyebrow", text: "YOUR SALES WORKSPACE" }),
          h("h1", { text: "Welcome back" }),
          h("p", {
            class: "muted",
            text: "Sign in to manage your team and track your sales activities."
          })
        ),
        form,
        demoDetails,
        h("p", {
          class: "login-footer",
          text: "FreeBees Sales CRM · Secure team access"
        })
      )
    )
  );

  email.focus();
}
