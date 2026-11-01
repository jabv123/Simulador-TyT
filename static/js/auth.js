import { api, clearSession, hasSession } from "./api.js";

let currentUser = null;

export async function login(credentials) {
  const tokens = await api("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify(credentials),
    auth: false,
    retry: false,
    clearOnUnauthorized: false,
  });
  if (!tokens.access || !tokens.refresh) {
    throw new Error("El servidor no devolvió los tokens de sesión.");
  }
  sessionStorage.setItem("tyt_access", tokens.access);
  sessionStorage.setItem("tyt_refresh", tokens.refresh);
  currentUser = tokens.usuario || null;
  return tokens;
}

export async function logout() {
  const refresh = sessionStorage.getItem("tyt_refresh");
  try {
    if (refresh) {
      await api("/api/auth/logout/", {
        method: "POST",
        body: JSON.stringify({ refresh }),
        auth: false,
        retry: false,
        clearOnUnauthorized: false,
      });
    }
  } finally {
    clearSession();
    currentUser = null;
  }
}

export async function getCurrentUser(force = false) {
  if (!hasSession()) {
    currentUser = null;
    return null;
  }
  if (force || !currentUser || !currentUser.permisos?.length) {
    currentUser = await api("/api/auth/me/");
  }
  return currentUser;
}

export function hasPermission(requiredPermission, user = currentUser) {
  if (!user) return false;
  const [module, action] = requiredPermission.toUpperCase().split(".", 2);
  if (!module || !action) return false;
  if (user.rol?.toLowerCase() === "administrador") return true;
  if (Array.isArray(user.permisos) && typeof user.permisos[0] === "string") {
    return user.permisos.some((permission) => permission.toUpperCase() === `${module}.${action}`);
  }
  return user.permisos?.some((permission) =>
    permission.modulo.toUpperCase() === module
    && permission.accion.toUpperCase() === action
  ) || false;
}

export function getAuthenticatedUser() {
  return currentUser;
}

export function guard({ permission } = {}) {
  if (!hasSession()) {
    window.location.assign("/");
    return false;
  }
  if (permission && !hasPermission(permission)) {
    window.location.assign(`/acceso-denegado/?permiso=${encodeURIComponent(permission)}`);
    return false;
  }
  return true;
}
