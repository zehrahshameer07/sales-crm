// One place that talks to the backend. Every request sends the session cookie automatically.
export class ApiError extends Error {
  constructor(status, detail, code, retryAfter) {
    super(typeof detail === "string" ? detail : "Request failed");
    this.status = status; this.detail = detail; this.code = code; this.retryAfter = retryAfter;
  }
}

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

function buildUrl(path, params) {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  }
  return url;
}

export async function api(path, { method = "GET", body, params } = {}) {
  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (response.status === 204) return null;
  let data = null;
  try { data = await response.json(); } catch { /* no body */ }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/api/auth/login")) onUnauthorized();
    throw new ApiError(response.status, data?.detail ?? "Something went wrong.", data?.code, response.headers.get("Retry-After"));
  }
  return data;
}

/** A readable message for any error. */
export function errorText(error) {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  if (Array.isArray(error.detail)) return error.detail.map((d) => d.msg.replace("Value error, ", "")).join(" ");
  return String(error.detail);
}

/** Map 422 validation errors to {fieldName: message}. */
export function fieldErrors(error) {
  const result = {};
  if (error instanceof ApiError && Array.isArray(error.detail)) {
    for (const item of error.detail) {
      const field = item.loc?.[item.loc.length - 1];
      if (field && !(field in result)) result[field] = item.msg.replace("Value error, ", "");
    }
  }
  return result;
}

/** Download a generated file (CSV/PDF). Errors become normal messages instead of a broken download. */
export async function download(path, params, filename) {
  let response;
  try {
    response = await fetch(buildUrl(path, params), { credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    let data = null;
    try { data = await response.json(); } catch { /* ignore */ }
    if (response.status === 401) onUnauthorized();
    throw new ApiError(response.status, data?.detail ?? "Download failed.");
  }
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 4000);
}
