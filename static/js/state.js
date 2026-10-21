// Shared app state (kept in memory only; the login session lives in an HttpOnly cookie)
export const state = {
  user: null,
  config: { demo_accounts: [], app_timezone: "Asia/Kolkata" },
  options: [],          // people the current user may filter by
  activityPreset: null, // filters to apply when the Activities page opens (e.g. from the Team page)
};
export const isAdmin = () => state.user?.role === "admin";
export const isLead = () => state.user?.role === "admin" || state.user?.role === "manager";
