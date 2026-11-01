const ACCESS_KEY = "tyt_access";
const REFRESH_KEY = "tyt_refresh";

let refreshInFlight = null;

export function clearSession() {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
}

export function hasSession() {
  return Boolean(sessionStorage.getItem(ACCESS_KEY));
}

async function refreshAccessToken() {
  const refresh = sessionStorage.getItem(REFRESH_KEY);
  if (!refresh) return false;

  if (!refreshInFlight) {
    refreshInFlight = fetch("/api/auth/refresh/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    })
      .then(async (response) => {
        if (!response.ok) return false;
        const tokens = await response.json();
        if (!tokens.access) return false;
        sessionStorage.setItem(ACCESS_KEY, tokens.access);
        if (tokens.refresh) sessionStorage.setItem(REFRESH_KEY, tokens.refresh);
        return true;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

function redirectToLogin() {
  clearSession();
  if (window.location.pathname !== "/") window.location.assign("/");
}

async function readBody(response) {
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json().catch(() => ({}));
  }
  return response.blob();
}

function getErrorMessage(body) {
  if (body?.detail) return body.detail;
  if (body && typeof body === "object" && !("size" in body)) {
    const messages = Object.entries(body).map(([field, value]) =>
      `${field}: ${Array.isArray(value) ? value.join(", ") : value}`
    );
    if (messages.length) return messages.join(" · ");
  }
  return "Ocurrió un error al procesar la solicitud.";
}

export async function api(url, options = {}) {
  const {
    auth = true,
    retry = true,
    clearOnUnauthorized = true,
    ...fetchOptions
  } = options;
  const headers = new Headers(fetchOptions.headers || {});
  const bodyIsFormData = fetchOptions.body instanceof FormData;
  if (auth) {
    const access = sessionStorage.getItem(ACCESS_KEY);
    if (access) headers.set("Authorization", `Bearer ${access}`);
  }
  if (fetchOptions.body && !bodyIsFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response = await fetch(url, { ...fetchOptions, headers });
  if (response.status === 401 && auth && retry && sessionStorage.getItem(REFRESH_KEY)) {
    let refreshed;
    try {
      refreshed = await refreshAccessToken();
    } catch (error) {
      if (clearOnUnauthorized) redirectToLogin();
      throw error;
    }
    if (refreshed) {
      const access = sessionStorage.getItem(ACCESS_KEY);
      if (access) headers.set("Authorization", `Bearer ${access}`);
      response = await fetch(url, { ...fetchOptions, headers });
    } else {
      response = new Response(JSON.stringify({
        detail: "La sesión expiró. Inicia sesión nuevamente.",
      }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (response.status === 401 && clearOnUnauthorized) redirectToLogin();
  } else if (
    response.status === 401
    && auth
    && clearOnUnauthorized
    && !sessionStorage.getItem(REFRESH_KEY)
  ) {
    redirectToLogin();
  }

  const body = await readBody(response);
  if (!response.ok) {
    const error = new Error(getErrorMessage(body));
    error.data = body;
    throw error;
  }
  return body;
}
