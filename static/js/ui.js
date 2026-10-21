// Small UI toolkit: element builder, icons, formatting, charts, dialogs, toasts.
// All user text goes through textContent (never innerHTML), so injected HTML can't run.
import { state } from "./state.js";

export function h(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "style") {
      for (const [name, val] of Object.entries(value)) {
        if (name.startsWith("--")) node.style.setProperty(name, val);   // CSS custom properties need setProperty
        else node.style[name] = val;
      }
    }
    else if (key === "on") for (const [evt, fn] of Object.entries(value)) node.addEventListener(evt, fn);
    else if (key === "data") for (const [k, v] of Object.entries(value)) node.dataset[k] = v;
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  for (const kid of kids.flat()) {
    if (kid === undefined || kid === null || kid === false) continue;
    node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return node;
}

const SVG_NS = "http://www.w3.org/2000/svg";
export function icon(name, cls = "") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", `icon ${cls}`.trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

// ---------------------------------------------------------------- labels
export const STATUS = { pending: "Pending", in_progress: "In progress", completed: "Completed" };
export const TYPE = { call: "Call", visit: "Visit", demo: "Demo", follow_up: "Follow-up" };
export const PRODUCT = { freebees_menu: "FreeBees Menu", freebees_play: "FreeBees Play", both: "Both products", none: "Not specified" };
export const ROLE = { admin: "Admin", manager: "Manager", salesperson: "Salesperson" };

export const statusBadge = (s) => h("span", { class: `badge ${s}`, text: STATUS[s] });
export const roleBadge = (r) => h("span", { class: `badge plain ${r}`, text: ROLE[r] });

export function initials(name) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}
export function avatar(name, size = "") {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % 6;
  return h("div", { class: `avatar av-${hash} ${size}`.trim(), "aria-hidden": "true", text: initials(name) });
}

// ----------------------------------------------------------------- dates
const pad = (n) => String(n).padStart(2, "0");
export const toISO = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseDay = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };

/** Today's date in the app's business timezone (India by default), as YYYY-MM-DD. */
export function appToday() {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone: state.config.app_timezone }).format(new Date());
  } catch {
    return toISO(new Date());
  }
}
export function addDays(iso, n) { const d = parseDay(iso); d.setDate(d.getDate() + n); return toISO(d); }

export function formatDay(iso) {
  if (!iso) return "";
  const today = parseDay(appToday());
  const date = parseDay(iso);
  const diff = Math.round((date - today) / 86400000);
  if (diff === 0) return "Today";
  if (diff === -1) return "Yesterday";
  if (diff === 1) return "Tomorrow";
  const options = { day: "numeric", month: "short" };
  if (date.getFullYear() !== today.getFullYear()) options.year = "numeric";
  return date.toLocaleDateString([], options);
}
export function timeAgo(iso) {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  if (seconds < 86400 * 7) return `${Math.floor(seconds / 86400)} d ago`;
  return new Date(iso).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}
export const fullDateTime = (iso) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
export const formatDays = (n) => (n === 0 ? "same day" : n === 1 ? "1 day" : `${n} days`);

// --------------------------------------------------------------- charts
export function ring(percent) {
  const r = 46, c = 2 * Math.PI * r;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 112 112");
  const mk = (cls, dash) => {
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("class", cls); circle.setAttribute("cx", "56"); circle.setAttribute("cy", "56");
    circle.setAttribute("r", String(r)); circle.setAttribute("fill", "none"); circle.setAttribute("stroke-width", "10");
    if (dash) circle.setAttribute("stroke-dasharray", dash);
    return circle;
  };
  svg.append(mk("track"), mk("value", `${(c * percent) / 100} ${c}`));
  return h("div", { class: "ring", role: "img", "aria-label": `${percent}% completed` }, svg,
    h("div", { class: "center" }, h("div", {}, `${percent}%`, h("small", { text: "completed" }))));
}

export function trend(days) {
  const max = Math.max(1, ...days.map((d) => d.count));
  const todayIso = appToday();
  return h("div", { class: "trend", role: "img", "aria-label": "Activities started in the last 7 days" },
    days.map((d) => h("div", { class: `trend-col ${d.date === todayIso ? "today" : ""}` },
      h("b", { text: String(d.count) }),
      h("div", { class: "trend-bar", style: { height: `${d.count ? Math.max(8, Math.round((d.count / max) * 92)) : 4}px` } }),
      h("span", { text: d.date === todayIso ? "Today" : parseDay(d.date).toLocaleDateString([], { weekday: "short" }) }))));
}

export function hbars(items, labels, { ok = false } = {}) {
  const max = Math.max(1, ...items.map((i) => i.count));
  return h("div", { class: "stack", style: { gap: "10px" } }, items.map((item) =>
    h("div", { class: "hbar" },
      h("span", { class: "ellipsis", text: labels[item.key] ?? item.key }),
      h("div", { class: "bar-track" }, h("div", { class: `bar-fill ${ok ? "ok" : ""}`, style: { width: `${(item.count / max) * 100}%` } })),
      h("span", { class: "num", text: String(item.count) }))));
}

export function percentBar(value) {
  return h("div", { class: "pct" },
    h("div", { class: "bar-track" }, h("div", { class: "bar-fill ok", style: { width: `${value}%` } })),
    h("span", { class: "small strong", text: `${value}%` }));
}

// --------------------------------------------------------------- pieces
export const skeletons = (n = 3, height = 110) =>
  Array.from({ length: n }, () => h("div", { class: "skeleton", style: { minHeight: `${height}px` } }));

export function emptyState(title, text, action) {
  return h("div", { class: "empty" }, icon("list"), h("strong", { text: title }), text && h("p", { text }), action);
}

export function card(title, body, actions) {
  return h("section", { class: "card" },
    title && h("div", { class: "card-head" }, h("h2", { text: title }), actions),
    body);
}

export function field(label, control, { hint, id } = {}) {
  const error = h("span", { class: "error-text", role: "alert" });
  const wrap = h("div", { class: "field" }, h("label", { for: id || control.id, text: label }), control,
    hint && h("span", { class: "hint", text: hint }), error);
  wrap.setError = (message) => { error.textContent = message || ""; control.classList.toggle("invalid", Boolean(message)); };
  return wrap;
}

export function select(id, options, value = "") {
  const el = h("select", { id, class: "input" }, options.map(([val, text]) => h("option", { value: val, text })));
  el.value = value;
  return el;
}

export function debounce(fn, ms = 300) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

// ------------------------------------------------------ toasts & dialogs
export function toast(message, type = "ok") {
  const box = document.getElementById("toasts");
  const node = h("div", { class: `toast ${type}`, role: type === "error" ? "alert" : "status" },
    icon(type === "error" ? "alert" : "check"), h("span", { text: message }));
  box.append(node);
  setTimeout(() => node.remove(), type === "error" ? 6000 : 3200);
}

export function openDialog({ title, body, footer = [], dismissible = true }) {
  const dialog = h("dialog", { class: "modal", "aria-label": title });
  const close = () => dialog.close();
  dialog.append(
    h("div", { class: "modal-head" }, h("h2", { text: title }),
      dismissible && h("button", { class: "btn sm icon-only", type: "button", "aria-label": "Close", on: { click: close } }, icon("x"))),
    h("div", { class: "modal-body" }, body),
    footer.length ? h("div", { class: "modal-foot" }, footer) : null);
  dialog.addEventListener("close", () => dialog.remove());
  if (dismissible) dialog.addEventListener("click", (e) => { if (e.target === dialog) close(); });
  else dialog.addEventListener("cancel", (e) => e.preventDefault());
  document.body.append(dialog);
  dialog.showModal();
  return { dialog, close };
}

export function confirmDialog({ title, message, confirmText = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    let answered = false;
    const finish = (value) => { answered = true; resolve(value); handle.close(); };
    const handle = openDialog({
      title, body: h("p", { text: message }),
      footer: [
        h("button", { class: "btn", type: "button", text: "Cancel", on: { click: () => finish(false) } }),
        h("button", { class: `btn ${danger ? "danger" : "primary"}`, type: "button", text: confirmText, on: { click: () => finish(true) } }),
      ],
    });
    handle.dialog.addEventListener("close", () => { if (!answered) resolve(false); });
  });
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied to clipboard"); }
  catch { toast("Select the text and copy it manually.", "error"); }
}
