
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

  const passwordToggle = h("button", {
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
  }, "Show");

  const passwordWrap = h(
    "div",
    { class: "login-password-wrap" },
    password,
    passwordToggle
  );

  const error = h("div", {
    class: "form-error",
    hidden: true,
    role: "alert"
  });

  const submit = h("button", {
    class: "btn primary block login-submit",
    type: "submit",
    text: "Sign in"
  });

  const infoBox = notice
    ? h(
        "div",
        { class: "callout" },
        icon("alert"),
        h("span", { text: notice })
      )
    : null;

  const form = h(
    "form",
    { class: "stack login-form", novalidate: true },
    infoBox,
    error,
    field("Work email", email),
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
    submit.textContent = "Signing in...";

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
          ? `${errorText(e)} (Retry in about ${Math.ceil(
              Number(e.retryAfter) / 60
            )} min.)`
          : errorText(e);

      password.value = "";
      password.focus();
      submit.disabled = false;
      submit.textContent = "Sign in";
    }
  });

  const demo = state.config.demo_accounts || [];
  console.log("Demo accounts:", demo);

  const demoDetails = demo.length
    ? h(
        "section",
        { class: "demo-box login-demo login-demo-visible" },
        h("div", { class: "login-demo-heading" },
          h("strong", { text: "Demo accounts" }),
          h("span", {
            class: "tiny muted",
            text: "Choose a role to try the CRM"
          })
        ),
        h(
          "div",
          { class: "demo-list" },
          demo.map((account) =>
            h(
              "div",
              { class: "demo-row" },
              h(
                "div",
                { class: "demo-account-info" },
                h("span", {
                  class: "strong",
                  text: account.role
                    ? account.role[0].toUpperCase() + account.role.slice(1)
                    : "Demo user"
                }),
                h("span", {
                  class: "tiny muted demo-email",
                  text: account.email
                })
              ),
              h("button", {
                class: "btn demo-use",
                type: "button",
                text: "Use account",
                on: {
                  click: () => {
                    email.value = account.email;
                    password.value = account.password || "";
                    password.type = "password";
                    passwordToggle.textContent = "Show";
                    passwordToggle.setAttribute(
                      "aria-label",
                      "Show password"
                    );
                    error.hidden = true;
                    email.focus();
                  }
                }
              })
            )
          )
        )
      )
    : null;

  const showcase = h(
    "aside",
    {
      class: "login-showcase",
      "aria-label": "FreeBees sales workspace"
    },
    h("div", { class: "login-showcase-top" },
      h("div", { class: "login-brand" },
        h("div", { class: "brand-mark" }, icon("chart", "lg")),
        h("div", {},
          h("div", {
            class: "login-brand-name",
            text: "FreeBees"
          }),
          h("div", {
            class: "login-brand-subtitle",
            text: "SALES CRM"
          })
        )
      ),
      h("span", {
        class: "login-workspace-tag",
        text: "YOUR WORKSPACE"
      })
    ),

    h("div", { class: "login-showcase-copy" },
      h("h1", {},
        "Every relationship,",
        h("br", {}),
        h("span", {
          class: "login-accent-text",
          text: "moving forward."
        })
      ),
      h("p", {
        text: "Keep customer conversations, daily activities and follow-ups organised in one place."
      })
    ),

    h("div", {
      class: "login-visual",
      "aria-hidden": "true"
    },
      h("div", { class: "login-visual-heading" },
        h("div", {},
          h("span", {
            class: "login-visual-kicker",
            text: "SALES OVERVIEW"
          }),
          h("div", {
            class: "login-visual-title",
            text: "Your team's momentum"
          })
        ),
        h("span", { class: "login-visual-dots" }, "•••")
      ),

      h("div", { class: "login-visual-metrics" },
        h("div", { class: "login-visual-metric" },
          h("span", { text: "Activities" }),
          h("strong", { text: "Track" }),
          h("span", {
            class: "login-metric-note",
            text: "Daily progress"
          })
        ),
        h("div", { class: "login-visual-metric" },
          h("span", { text: "Follow-ups" }),
          h("strong", { text: "Connect" }),
          h("span", {
            class: "login-metric-note",
            text: "Stay on track"
          })
        )
      ),

      h("div", { class: "login-chart-card" },
        h("div", { class: "login-chart-heading" },
          h("span", { text: "Activity at a glance" }),
          h("span", {
            class: "login-chart-label",
            text: "WEEKLY"
          })
        ),

        h(
          "div",
          { class: "login-chart" },
          ...[32, 52, 40, 72, 48, 86, 62].map((height, index) =>
            h("div", { class: "login-chart-column" },
              h("span", {
                class: `login-chart-bar${
                  index === 5 ? " is-highlighted" : ""
                }`,
                style: { height: `${height}%` }
              })
            )
          )
        ),

        h(
          "div",
          { class: "login-chart-days" },
          ...["M", "T", "W", "T", "F", "S", "S"].map((day) =>
            h("span", { text: day })
          )
        )
      )
    ),

    h("div", { class: "login-showcase-bottom" },
      h("span", { class: "login-status-dot" }),
      h("span", {
        text: "One workspace. A clearer view of every next step."
      })
    )
  );

  const loginPanel = h(
    "section",
    {
      class: "login-panel",
      "aria-label": "Sign in"
    },
    h("div", { class: "login-panel-inner" },

      h("div", { class: "login-mobile-brand" },
        h("div", { class: "brand-mark" }, icon("chart", "lg")),
        h("span", {
          class: "login-brand-name",
          text: "FreeBees"
        })
      ),

      h("div", { class: "login-heading" },
        h("h2", { text: "Sign in to your account" }),
        h("p", {
          class: "muted",
          text: "Enter your details to access your sales workspace."
        })
      ),

      form,
      demoDetails,

      h("p", {
        class: "login-footer",
        text: "FreeBees Sales CRM · Secure team access"
      })
    )
  );

  root.replaceChildren(
    h(
      "div",
      { class: "login login-modern login-split" },
      showcase,
      loginPanel
    )
  );
}
