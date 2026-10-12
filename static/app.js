// =====================================================================
// Sales CRM frontend (plain JavaScript, no build step)
// =====================================================================

// ---------- Helpers ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function api(path, options) {
  try {
    const res = await fetch(path, options);
    let data = null;
    try { data = await res.json(); } catch { /* empty body */ }
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: null };   // network error
  }
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// ---------- Dates ----------
// Start / end dates are plain days like "2026-10-09" (no time, no timezone).
function toISODate(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
}

function parseDay(value) {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function formatDay(value) {
  const d = parseDay(value);
  const today = parseDay(toISODate(new Date()));
  const diff = Math.round((today - d) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  const options = { day: "numeric", month: "short" };
  if (d.getFullYear() !== today.getFullYear()) options.year = "numeric";
  return d.toLocaleDateString([], options);
}

function daysBetween(start, end) {
  return Math.max(0, Math.round((parseDay(end) - parseDay(start)) / 86400000));
}

function formatDays(n) {
  if (n === 0) return "same day";
  return n === 1 ? "1 day" : n + " days";
}

let toastTimer;
function showToast(message, type) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = "toast show" + (type === "error" ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

// ---------- State ----------
const state = { view: "dashboard", period: "all", listPeriod: "all", status: "", search: "" };

// Demo user (there is no login). 
const DEFAULT_USER = {
  name: "Demo User",
  role: "Sales Executive",
  email: "demo.user@freebees.com",
  phone: "+91 90000 00000",
  region: "Bengaluru",
  employeeId: "FB-DEMO-001",
};

// Status can only move forward. Completed is final. (The server enforces this too.)
const NEXT_STATUS = {
  "Pending": ["In Progress", "Completed"],
  "In Progress": ["Completed"],
  "Completed": [],
};
const STATUS_BUTTON_LABEL = { "In Progress": "Start work", "Completed": "Mark completed" };

// Turn an API error response into a message a person can read
function errorMessage(status, body, fallback) {
  if (status === 0) return "Can't reach the server. Check your connection.";
  if (body && typeof body.detail === "string") return body.detail;
  return fallback;
}

// ---------- Activity card ----------
function avatar(name) {
  const words = name.trim().split(/\s+/);
  const initials = (words[0][0] + (words[1] ? words[1][0] : "")).toUpperCase();
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 6;
  const node = el("div", "avatar av-" + hash, initials);
  node.setAttribute("aria-hidden", "true");
  return node;
}

// "Started Yesterday · Completed Today · took 1 day"
function describeDates(a) {
  let text = "Started " + formatDay(a.start_date);
  if (a.end_date) {
    const days = daysBetween(a.start_date, a.end_date);
    text += " \u00b7 Completed " + formatDay(a.end_date) +
            (days === 0 ? " \u00b7 same day" : " \u00b7 took " + formatDays(days));
  }
  return text;
}

function buildCard(a) {
  const card = el("article", "activity");
  card.appendChild(avatar(a.customer_name));

  const body = el("div", "activity-body");
  const top = el("div", "activity-top");
  top.append(
    el("h3", "activity-name", a.customer_name),
    el("span", "pill " + a.status.replace(" ", "-"), a.status)
  );

  const chips = el("div", "chips");
  chips.appendChild(el("span", "chip chip-type", a.activity_type));
  if (a.product_interested) chips.appendChild(el("span", "chip", a.product_interested));
  if (a.location) chips.appendChild(el("span", "chip", a.location));
  if (a.contact) chips.appendChild(el("span", "chip", a.contact));

  body.append(top, chips);
  if (a.notes) body.appendChild(el("p", "activity-notes", a.notes));
  body.appendChild(el("p", "activity-time", describeDates(a)));
  body.appendChild(buildActions(a));
  card.appendChild(body);
  return card;
}

// Edit button + the status buttons that are allowed for this activity
function buildActions(a) {
  const actions = el("div", "activity-actions");

  const editBtn = el("button", "btn-sm", "Edit");
  editBtn.type = "button";
  editBtn.addEventListener("click", () => openForm(a));
  actions.appendChild(editBtn);

  const nextOptions = NEXT_STATUS[a.status] || [];
  nextOptions.forEach((nextStatus) => {
    const btn = el("button", "btn-sm btn-status", STATUS_BUTTON_LABEL[nextStatus]);
    btn.type = "button";
    btn.addEventListener("click", () => changeStatus(a, nextStatus, btn));
    actions.appendChild(btn);
  });

  if (nextOptions.length === 0) {
    actions.appendChild(el("span", "locked-note", "Completed, status is locked"));
  }
  return actions;
}

async function changeStatus(a, newStatus, btn) {
  if (newStatus === "Completed" &&
      !confirm("Mark this activity as completed today? Completed activities cannot be moved back. " +
               "(You can change the end date later with Edit.)")) {
    return;
  }
  btn.disabled = true;
  const { ok, status, data } = await api("/api/activities/" + a.id, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: newStatus }),
  });
  if (ok) {
    showToast("Status changed to " + newStatus);
    await refresh();
  } else {
    showToast(errorMessage(status, data, "Couldn't change the status. Try again."), "error");
    btn.disabled = false;
  }
}

function renderList(container, items, emptyText) {
  container.replaceChildren();
  if (items.length === 0) {
    container.appendChild(el("p", "empty", emptyText));
    return;
  }
  items.forEach((a) => container.appendChild(buildCard(a)));
}

// ---------- Dashboard ----------
function renderTrend(days) {
  const box = $("#trend");
  box.replaceChildren();
  const max = Math.max(1, ...days.map((d) => d.count));

  days.forEach((d, i) => {
    const isToday = i === days.length - 1;
    const col = el("div", "trend-col" + (isToday ? " today" : ""));
    const track = el("div", "trend-track");
    const bar = el("div", "trend-bar");
    bar.style.height = (d.count === 0 ? 3 : Math.max(8, Math.round((d.count / max) * 96))) + "px";
    track.append(el("span", "trend-value", String(d.count)), bar);
    col.append(track, el("span", "trend-label", isToday ? "Today" : d.label));
    box.appendChild(col);
  });

  const total = days.reduce((sum, d) => sum + d.count, 0);
  $("#trend-total").textContent = total + (total === 1 ? " activity" : " activities");
}

function renderBreakdown(id, items) {
  const box = $("#" + id);
  box.replaceChildren();
  const max = Math.max(1, ...items.map((i) => i.count));
  items.forEach((item) => {
    const row = el("div", "bar-row");
    const track = el("div", "bar-track");
    const fill = el("div", "bar-fill");
    fill.style.width = (item.count / max) * 100 + "%";
    track.appendChild(fill);
    row.append(el("span", "bar-label", item.label), track, el("span", "bar-count", String(item.count)));
    box.appendChild(row);
  });
}

// "Time to complete" card: average / fastest / slowest days from start date to end date
function renderPerformance(s) {
  if (s.avg_days_to_complete === null) {
    $("#perf-avg").textContent = "\u2013";
    $("#perf-unit").textContent = "";
    $("#perf-fastest").textContent = "\u2013";
    $("#perf-slowest").textContent = "\u2013";
    $("#perf-note").textContent = "Complete an activity (with an end date) to see how fast you close them.";
    return;
  }
  $("#perf-avg").textContent = s.avg_days_to_complete;
  $("#perf-unit").textContent = s.avg_days_to_complete === 1 ? " day on average" : " days on average";
  $("#perf-fastest").textContent = formatDays(s.fastest_days);
  $("#perf-slowest").textContent = formatDays(s.slowest_days);
  $("#perf-note").textContent = "Based on " + s.timed_count + " completed " +
    (s.timed_count === 1 ? "activity" : "activities") + " with an end date.";
}

async function loadDashboard() {
  $("#dash-date").textContent = new Date().toLocaleDateString([], {
    weekday: "long", day: "numeric", month: "long",
  });

  const [stats, list] = await Promise.all([
    api("/api/stats?period=" + state.period),
    api("/api/activities?period=" + state.period),
  ]);

  if (!stats.ok || !list.ok) {
    showToast("Could not load the dashboard. Please refresh.", "error");
    return;
  }

  const s = stats.data;
  $("#kpi-total").textContent = s.total;
  $("#kpi-pending").textContent = s.pending;
  $("#kpi-progress").textContent = s.in_progress;
  $("#kpi-completed").textContent = s.completed;
  $("#rate-value").textContent = s.completion_rate;
  $("#rate-fill").style.width = s.completion_rate + "%";

  renderTrend(s.last_7_days);
  renderPerformance(s);
  renderBreakdown("by-type", s.by_type);
  renderBreakdown("by-product", s.by_product);
  renderList($("#recent-list"), list.data.slice(0, 5), "No activities in this period yet.");
}

// ---------- Activities page ----------
async function loadActivities() {
  const params = new URLSearchParams({ period: state.listPeriod });
  if (state.status) params.set("status", state.status);
  if (state.search) params.set("search", state.search);

  const { ok, data } = await api("/api/activities?" + params.toString());
  const container = $("#activity-list");

  if (!ok) {
    container.replaceChildren(el("p", "empty", "Could not load activities. Please refresh."));
    return;
  }

  const filtered = state.status || state.search || state.listPeriod !== "all";
  $("#list-count").textContent = data.length + (data.length === 1 ? " activity" : " activities");
  renderList(
    container,
    data,
    filtered ? "No activities match these filters." : "No activities yet. Tap the + button to add your first one."
  );
}

// ---------- Routing (#/dashboard, #/activities) ----------
function route() {
  state.view = location.hash === "#/activities" ? "activities" : "dashboard";
  $$(".view").forEach((v) => (v.hidden = v.id !== "view-" + state.view));
  $$("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === state.view));
  window.scrollTo(0, 0);
  refresh();
}

function refresh() {
  return state.view === "dashboard" ? loadDashboard() : loadActivities();
}

window.addEventListener("hashchange", route);

// Period selector (dashboard)
$("#period-seg").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-period]");
  if (!btn) return;
  state.period = btn.dataset.period;
  $$("#period-seg button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  loadDashboard();
});

// Filters (activities page)
$("#status-chips").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-status]");
  if (!btn) return;
  state.status = btn.dataset.status;
  $$("#status-chips button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  loadActivities();
});

$("#list-period").addEventListener("change", (e) => {
  state.listPeriod = e.target.value;
  loadActivities();
});

$("#search").addEventListener("input", debounce((e) => {
  state.search = e.target.value.trim();
  loadActivities();
}, 300));

// ---------- Add / edit activity form ----------
const sheet = $("#sheet");
const form = $("#activity-form");
const formMessage = $("#form-message");
const submitBtn = $("#submit-btn");
let editingId = null;   // null = adding a new activity, a number = editing that activity

function showFormMessage(text, type) {
  formMessage.textContent = text;
  formMessage.className = "message " + (type || "");
}

function clearErrors() {
  $$(".field-error").forEach((n) => (n.textContent = ""));
  $$(".invalid").forEach((n) => n.classList.remove("invalid"));
  showFormMessage("", "");
}

function setFieldError(field, text) {
  const err = document.getElementById("err-" + field);
  const input = document.getElementById(field);
  if (err) err.textContent = text;
  if (input) input.classList.add("invalid");
}

// Only allow the statuses this activity may move to (new activities can pick any)
function setStatusOptions(currentStatus) {
  const select = $("#status");
  const hint = $("#status-hint");
  const allowed = currentStatus ? [currentStatus, ...NEXT_STATUS[currentStatus]] : null;

  [...select.options].forEach((opt) => {
    opt.disabled = Boolean(allowed && opt.value && !allowed.includes(opt.value));
  });
  select.disabled = currentStatus === "Completed";

  if (currentStatus === "Completed") hint.textContent = "Completed activities can't change status.";
  else if (currentStatus) hint.textContent = "Status can only move forward, not back.";
  else hint.textContent = "";
}

// The end date only makes sense once the activity is completed
function syncEndDate() {
  const completed = $("#status").value === "Completed";
  const end = $("#end_date");
  end.disabled = !completed;
  if (!completed) end.value = "";
  $("#end-hint").textContent = completed
    ? "When it was completed. Leave blank to use today."
    : "Available once the status is Completed.";
}
$("#status").addEventListener("change", syncEndDate);

// openForm()  -> add a new activity.   openForm(activity) -> edit that activity.
function openForm(activity) {
  clearErrors();
  form.reset();
  editingId = activity ? activity.id : null;

  const today = toISODate(new Date());
  $("#start_date").max = today;     // can't pick a future day
  $("#end_date").max = today;

  $("#sheet-title").textContent = activity ? "Edit activity" : "Add activity";
  submitBtn.textContent = activity ? "Save changes" : "Save activity";

  $("#start_date").value = activity ? activity.start_date : today;
  if (activity) {
    $("#customer_name").value = activity.customer_name;
    $("#activity_type").value = activity.activity_type;
    $("#status").value = activity.status;
    $("#end_date").value = activity.end_date || "";
    $("#contact").value = activity.contact || "";
    $("#location").value = activity.location || "";
    $("#product_interested").value = activity.product_interested || "";
    $("#notes").value = activity.notes || "";
  }
  setStatusOptions(activity ? activity.status : null);
  syncEndDate();

  sheet.showModal();
  $("#customer_name").focus();
}

function closeForm() {
  sheet.close();
}

$$("[data-open-form]").forEach((btn) => btn.addEventListener("click", () => openForm()));
$("#sheet-close").addEventListener("click", closeForm);
$("#cancel-btn").addEventListener("click", closeForm);
sheet.addEventListener("click", (e) => { if (e.target === sheet) closeForm(); });   // click on backdrop

function validate(data) {
  let valid = true;
  const today = toISODate(new Date());

  if (data.customer_name.length < 2) {
    setFieldError("customer_name", "Enter at least 2 characters.");
    valid = false;
  }
  if (!data.activity_type) { setFieldError("activity_type", "Select a type."); valid = false; }
  if (!data.status) { setFieldError("status", "Select a status."); valid = false; }

  if (!data.start_date) {
    setFieldError("start_date", "Pick the start date.");
    valid = false;
  } else if (data.start_date > today) {
    setFieldError("start_date", "Start date can't be in the future.");
    valid = false;
  }
  if (data.end_date) {
    if (data.start_date && data.end_date < data.start_date) {
      setFieldError("end_date", "End date can't be before the start date.");
      valid = false;
    } else if (data.end_date > today) {
      setFieldError("end_date", "End date can't be in the future.");
      valid = false;
    }
  }

  if (data.contact && !/^[0-9+\-\s()]{7,20}$/.test(data.contact)) {
    setFieldError("contact", "Enter a valid phone number.");
    valid = false;
  }
  return valid;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearErrors();

  const value = (id) => document.getElementById(id).value.trim();
  const data = {
    customer_name: value("customer_name"),
    activity_type: value("activity_type"),
    status: value("status"),
    start_date: value("start_date"),
    end_date: value("end_date"),
    contact: value("contact"),
    location: value("location"),
    product_interested: value("product_interested"),
    notes: value("notes"),
  };

  if (!validate(data)) {
    showFormMessage("Fix the highlighted fields and try again.", "error");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "Saving...";

  const isEdit = editingId !== null;
  const { ok, status, data: body } = await api(
    isEdit ? "/api/activities/" + editingId : "/api/activities",
    {
      method: isEdit ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }
  );

  if (ok) {
    form.reset();
    closeForm();
    showToast(isEdit ? "Activity updated" : "Activity saved");
    await refresh();
  } else if (status === 422 && body && Array.isArray(body.detail)) {
    // Show the server's validation errors next to the right field
    body.detail.forEach((d) => setFieldError(d.loc[d.loc.length - 1], d.msg.replace("Value error, ", "")));
    showFormMessage("The server rejected some values. Check the form.", "error");
  } else {
    showFormMessage(errorMessage(status, body, "Couldn't save. Try again."), "error");
  }

  submitBtn.disabled = false;
  submitBtn.textContent = isEdit ? "Save changes" : "Save activity";
});

// ---------- User menu (demo user) ----------
const userBtn = $("#user-btn");
const userPanel = $("#user-panel");
const loggedOut = $("#logged-out");

function initials(name) {
  return name.split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
}

function fillUserDetails() {
  $("#user-avatar").textContent = initials(DEFAULT_USER.name);
  $("#user-name").textContent = DEFAULT_USER.name;
  $("#user-role").textContent = DEFAULT_USER.role;
  $("#user-email").textContent = DEFAULT_USER.email;
  $("#user-phone").textContent = DEFAULT_USER.phone;
  $("#user-region").textContent = DEFAULT_USER.region;
  $("#user-id").textContent = DEFAULT_USER.employeeId;
}

function setUserPanel(open) {
  userPanel.hidden = !open;
  userBtn.setAttribute("aria-expanded", String(open));
}

userBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  setUserPanel(userPanel.hidden);
});
userPanel.addEventListener("click", (e) => e.stopPropagation());
document.addEventListener("click", () => setUserPanel(false));          // click outside closes it
document.addEventListener("keydown", (e) => { if (e.key === "Escape") setUserPanel(false); });

$("#logout-btn").addEventListener("click", () => {
  setUserPanel(false);
  loggedOut.hidden = false;
});
$("#login-again-btn").addEventListener("click", () => {
  loggedOut.hidden = true;
  showToast("Welcome back, " + DEFAULT_USER.name.split(" ")[0]);
});

fillUserDetails();

// ---------- Start ----------
route();