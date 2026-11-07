import { api } from "./api.js";
import {
  getCurrentUser,
  hasPermission as userHasPermission,
  login as authenticate,
  logout as endSession,
  guard,
} from "./auth.js";
import {
  initializeFormValidation,
  renderPagination,
  renderTable,
  showToast,
} from "./components.js";
import { formatDateParts, formatDateTime } from "./dateUtils.js";

(() => {
  "use strict";

  const app = document.querySelector("#app");
  const loginView = document.querySelector("#login-view");
  const dashboardView = document.querySelector("#dashboard-view");
  const navigation = document.querySelector("#navigation");
  const pageContent = document.querySelector("#page-content");
  const notice = document.querySelector("#notice");
  const loginMessage = document.querySelector("#login-message");
  const loginForm = document.querySelector("#login-form");
  const logoutButton = document.querySelector("#logout-button");
  const accountName = document.querySelector("#account-name");
  const sidebarToggle = document.querySelector("#sidebar-toggle");
  const endpoints = {
    profile: "/api/auth/me/",
    users: "/api/usuarios/",
    roles: "/api/auth/roles/",
    permissions: "/api/auth/permisos/",
    categories: "/api/categorias/",
    questions: "/api/preguntas/",
    quizzes: "/api/cuestionarios/",
    available: "/api/cuestionarios/disponibles/",
    imports: "/api/importaciones/",
    history: "/api/importaciones/historial/",
    results: "/api/resultados/",
    config: "/api/configuracion/administracion/",
  };
  let profile = null;
  let activePage = "home";
  let answerQueue = Promise.resolve();
  let usersPage = 1;
  let usersFilters = { search: "", rol: "", estado: "" };
  let questionsPage = 1;
  let questionFilters = { search: "", categoria: "", tipo: "", estado: "" };
  let resultsFilters = { cuestionario_id: "", usuario_id: "" };

  if (sidebarToggle && dashboardView) {
    sidebarToggle.addEventListener("click", () => {
      dashboardView.classList.toggle("sidebar-collapsed");
      const isCollapsed = dashboardView.classList.contains("sidebar-collapsed");
      sidebarToggle.textContent = isCollapsed ? "⟩" : "⟨";
      sidebarToggle.setAttribute("aria-label", isCollapsed ? "Expandir panel" : "Contraer panel");
      sidebarToggle.setAttribute("title", isCollapsed ? "Expandir panel" : "Contraer panel");
    });
  }

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);

  const formatImportDetail = (value) => {
    if (!value) return "—";
    const normalized = String(value).trim();
    if (!normalized || normalized === "—") return "—";

    try {
      const parsedValue = JSON.parse(normalized);
      const parsed = Array.isArray(parsedValue)
        ? { errores: parsedValue }
        : parsedValue;
      if (parsed && typeof parsed === "object") {
        const groups = [
          ["duplicadas", "Duplicadas"],
          ["errores", "Con errores"],
          ["validas", "Válidas"],
        ]
          .map(([key, title]) => {
            const entries = Array.isArray(parsed[key]) ? parsed[key] : [];
            if (!entries.length) return "";
            const items = entries.slice(0, 5).map((entry) => {
              if (typeof entry === "string") return escapeHtml(entry);
              if (typeof entry === "object") {
                const row = entry.fila ? `Fila ${escapeHtml(entry.fila)}: ` : "";
                return `${row}${escapeHtml(entry.motivo || entry.error || entry.datos?.enunciado || "Registro inválido")}`;
              }
              return escapeHtml(String(entry));
            }).join("<br>");
            return `<div class="import-detail-block"><strong>${title}</strong><div>${items}</div></div>`;
          })
          .filter(Boolean)
          .join("");
        if (groups) return groups;
      }
    } catch (error) {
      return escapeHtml(normalized.length > 180 ? `${normalized.slice(0, 177)}...` : normalized);
    }

    return escapeHtml(normalized.length > 180 ? `${normalized.slice(0, 177)}...` : normalized);
  };

  const getImportHistoryKinds = (item) => {
    const kinds = [];
    if (Number(item.registros_exitosos) > 0) kinds.push("validas");
    if (Number(item.registros_duplicados) > 0) kinds.push("duplicadas");
    if (Number(item.registros_con_errores) > 0) kinds.push("errores");
    return kinds.join(" ") || "all";
  };

  async function fetchAllPages(endpoint, query = {}) {
    const records = [];
    let page = 1;
    let next = true;
    while (next) {
      const params = new URLSearchParams({ ...query, page: String(page), page_size: "100" });
      const response = await api(`${endpoint}?${params}`);
      if (Array.isArray(response)) return response;
      records.push(...(response.results || []));
      next = Boolean(response.next);
      page += 1;
    }
    return records;
  }

  function showFieldErrors(form, error) {
    form.querySelectorAll("[data-field-error]").forEach((node) => node.remove());
    form.querySelectorAll(".is-invalid").forEach((node) => node.classList.remove("is-invalid"));
    let hasFieldError = false;
    for (const [field, messages] of Object.entries(error.data || {})) {
      const input = form.elements.namedItem(field);
      if (!input || !(input instanceof HTMLElement)) continue;
      hasFieldError = true;
      input.classList.add("is-invalid");
      const message = document.createElement("small");
      message.className = "field-error";
      message.dataset.fieldError = "";
      message.textContent = Array.isArray(messages)
        ? messages.join(" ")
        : String(messages);
      input.closest("label")?.append(message);
    }
    if (!hasFieldError && error.message) {
      const message = document.createElement("small");
      message.className = "field-error";
      message.dataset.fieldError = "";
      message.textContent = error.message;
      form.prepend(message);
    }
  }

  function showMessage(text, kind = "") {
    notice.textContent = text;
    notice.className = `message ${kind}`;
    if (text) showToast(text, kind === "error" ? "error" : "success");
  }

  const hasPermission = (module, action) =>
    userHasPermission(`${module}.${action}`, profile)
    || profile?.permisos?.some((permission) =>
      typeof permission === "string"
      && permission.toUpperCase() === `${module}.${action}`.toUpperCase()
    )
    || profile?.rol?.toLowerCase() === "administrador";

  function buildNavigation() {
    const pages = [{ id: "home", label: "Inicio" }];
    if (["VER", "CREAR", "EDITAR", "DESACTIVAR"].some((action) => hasPermission("USUARIOS", action))) {
      pages.push({ id: "users", label: "Usuarios" });
    }
    if (["VER", "CREAR", "EDITAR", "DESACTIVAR"].some((action) => hasPermission("ROLES", action))) {
      pages.push({ id: "roles", label: "Roles y permisos" });
    }
    if (
      hasPermission("CATEGORIAS", "VER")
      || hasPermission("CATEGORIAS", "CREAR")
      || hasPermission("CATEGORIAS", "EDITAR")
      || hasPermission("CATEGORIAS", "DESACTIVAR")
      || hasPermission("PREGUNTAS", "CREAR")
      || hasPermission("PREGUNTAS", "EDITAR")
      || hasPermission("PREGUNTAS", "DESACTIVAR")
      || hasPermission("PREGUNTAS", "VER")
    ) {
      pages.push({ id: "questions", label: "Banco de preguntas" });
    }
    if (
      hasPermission("CUESTIONARIOS", "GESTIONAR")
      || hasPermission("CUESTIONARIOS", "VER")
      || hasPermission("CUESTIONARIOS", "CREAR")
      || hasPermission("CUESTIONARIOS", "EDITAR")
      || hasPermission("CUESTIONARIOS", "DESACTIVAR")
    ) {
      pages.push({ id: "quizzes", label: "Cuestionarios" });
    }
    if (
      hasPermission("IMPORTACION", "IMPORTAR")
      || hasPermission("IMPORTACIONES", "IMPORTAR")
      || hasPermission("IMPORTACIONES", "CREAR")
      || hasPermission("IMPORTACIONES", "VER")
    ) {
      pages.push({ id: "imports", label: "Importar Excel" });
    }
    if (hasPermission("CONFIGURACION", "EDITAR")) {
      pages.push({ id: "config", label: "Configuración" });
    }
    if (hasPermission("CUESTIONARIOS", "VER_DISPONIBLES")) {
      pages.push({ id: "available", label: "Presentar prueba" });
    }
    if (hasPermission("RESULTADOS", "VER") || hasPermission("RESULTADOS", "VER_PROPIA_NOTA")) {
      pages.push({ id: "results", label: "Resultados" });
    }
    if (hasPermission("REPORTES", "VER")) {
      pages.push({ id: "reports", label: "Consultas y reportes" });
    }
    navigation.innerHTML = pages.map((page) =>
      `<button class="nav-link ${activePage === page.id ? "active" : ""}" data-page="${page.id}">${page.label}</button>`
    ).join("");
    navigation.querySelectorAll("[data-page]").forEach((button) => {
      button.addEventListener("click", () => loadPage(button.dataset.page));
    });
  }

  function renderHome() {
    const permissionCount = profile.permisos?.length || 0;
      const rolEstudiante = profile.rol?.toLowerCase() === "estudiante";
      pageContent.innerHTML = `
      <div class="page-header"><div><p class="eyebrow">Resumen</p><h1>Hola, ${escapeHtml(profile.nombre)}</h1>
        <p>${rolEstudiante ? "Consulta cuestionarios disponibles y revisa tus resultados." : "Administra el banco de preguntas, los cuestionarios y el seguimiento académico."}</p></div><span class="badge">${escapeHtml(profile.rol)}</span></div>
      <div class="grid-cards">
        <article class="card"><p class="eyebrow">Cuenta</p><h3>${escapeHtml(profile.codigo)}</h3><p>${escapeHtml(profile.correo)}</p></article>
        <article class="card"><p class="eyebrow">Acceso</p><h3>${permissionCount} permisos asignados</h3><p>Las acciones se validan también en el servidor.</p></article>
        <article class="card"><p class="eyebrow">Estado</p><h3>${escapeHtml(profile.estado)}</h3><p>Consulta las opciones habilitadas en el menú.</p></article>
      </div>`;
  }

  async function loadUsers(page = usersPage) {
    usersPage = page;
    const params = new URLSearchParams({ page: String(usersPage) });
    Object.entries(usersFilters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const [pageData, roles] = await Promise.all([
      api(`${endpoints.users}?${params}`),
      ["CREAR", "EDITAR"].some((action) => hasPermission("USUARIOS", action))
        ? api(endpoints.roles)
        : Promise.resolve([]),
    ]);
    const users = pageData.results || pageData;
    pageContent.innerHTML = `
      <div class="page-header"><div><p class="eyebrow">Administración</p><h1>Usuarios</h1><p>Crea cuentas y asígnales un rol.</p></div></div>
      <section class="card"><h2>Crear usuario</h2>
        <form id="user-form" class="form-grid">
          <label>Nombre<input name="nombre" required maxlength="150"></label>
          <label>Código<input name="codigo" required maxlength="30"></label>
          <label>Correo<input name="correo" type="email" required maxlength="150"></label>
          <label>Contraseña temporal<input name="password" type="password" required minlength="8"></label>
          <label>Rol<select name="rol" required>${roles.map((role) => `<option value="${role.id}">${escapeHtml(role.nombre)}</option>`).join("")}</select></label>
          <div class="toolbar"><button class="button button-primary">Crear usuario</button></div>
        </form>
      </section>
      <section class="section"><h2>Cuentas registradas</h2>
      <form id="users-filter" class="form-grid">
        <label>Buscar<input name="search" value="${escapeHtml(usersFilters.search)}" placeholder="Nombre, código, correo o teléfono"></label>
        <label>Rol<select name="rol"><option value="">Todos los roles</option>${roles.map((role) => `<option value="${role.id}" ${String(usersFilters.rol) === String(role.id) ? "selected" : ""}>${escapeHtml(role.nombre)}</option>`).join("")}</select></label>
        <label>Estado<select name="estado"><option value="">Todos los estados</option><option value="ACTIVO" ${usersFilters.estado === "ACTIVO" ? "selected" : ""}>Activo</option><option value="INACTIVO" ${usersFilters.estado === "INACTIVO" ? "selected" : ""}>Inactivo</option></select></label>
        <div class="toolbar"><button class="button button-quiet">Filtrar</button></div>
      </form>${renderTable(
        ["Nombre", "Código", "Correo", "Rol", "Estado", "Acción"],
        users.map((user) => `<tr><td>${escapeHtml(user.nombre)}</td><td>${escapeHtml(user.codigo)}</td><td>${escapeHtml(user.correo)}</td><td>${escapeHtml(user.rol_nombre)}</td><td>${escapeHtml(user.estado)}</td><td><button class="button button-quiet" data-toggle-user="${user.id}" data-state="${escapeHtml(user.estado)}">${user.estado === "ACTIVO" ? "Desactivar" : "Activar"}</button><button class="button button-quiet" data-reset-password="${user.id}">Restablecer contraseña</button></td></tr>`)
      )}${renderPagination({ page: usersPage, hasPrevious: Boolean(pageData.previous), hasNext: Boolean(pageData.next), previousId: "users-prev", nextId: "users-next" })}</section>`;
    const createForm = document.querySelector("#user-form");
    const createSection = createForm.closest(".card");
    createSection.hidden = true;
    const createButton = document.createElement("button");
    createButton.className = "button button-primary";
    createButton.type = "button";
    createButton.textContent = "Crear usuario";
    createButton.hidden = !hasPermission("USUARIOS", "CREAR");
    document.querySelector(".page-header").append(createButton);
    let createModal = null;
    createButton.addEventListener("click", () => {
      createForm.reset();
      createModal = openModal({ title: "Crear usuario", content: createForm });
    });
    const usersTable = [...pageContent.querySelectorAll(".table-wrap")]
      .find((table) => table.closest("section")?.querySelector("h2")?.textContent === "Cuentas registradas");
    usersTable?.querySelectorAll("[data-table-row]").forEach((row, index) => {
      const user = users[index];
      const actionCell = row.lastElementChild;
      if (!hasPermission("USUARIOS", "DESACTIVAR")) {
        actionCell.querySelector("[data-toggle-user]")?.remove();
      }
      if (!hasPermission("USUARIOS", "EDITAR")) {
        actionCell.querySelector("[data-reset-password]")?.remove();
      }
      if (!user || !hasPermission("USUARIOS", "EDITAR")) return;
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "button button-quiet";
      editButton.textContent = "Editar";
      editButton.addEventListener("click", () => {
        const form = document.createElement("form");
        form.className = "form-grid";
        form.innerHTML = `
          <label>Nombre<input name="nombre" value="${escapeHtml(user.nombre)}" required maxlength="150"></label>
          <label>Código<input name="codigo" value="${escapeHtml(user.codigo)}" required maxlength="30"></label>
          <label>Correo<input name="correo" type="email" value="${escapeHtml(user.correo)}" required maxlength="150"></label>
          <label>Rol<select name="rol" required>${roles.map((role) => `<option value="${role.id}" ${Number(user.rol) === Number(role.id) ? "selected" : ""}>${escapeHtml(role.nombre)}</option>`).join("")}</select></label>
          <label>Teléfono<input name="telefono" value="${escapeHtml(user.telefono || "")}" maxlength="20"></label>
          <label>Foto<input name="foto" value="${escapeHtml(user.foto || "")}" maxlength="255"></label>
          <label>Nueva contraseña (opcional)<input name="password" type="password" minlength="8" autocomplete="new-password"></label>
          <div class="toolbar"><button class="button button-primary">Guardar cambios</button></div>`;
        const modal = openModal({ title: `Editar ${user.nombre}`, content: form });
        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          if (!form.reportValidity()) return;
          const data = Object.fromEntries(new FormData(form));
          data.rol = Number(data.rol);
          if (!data.password) delete data.password;
          try {
            await api(`${endpoints.users}${user.id}/`, { method: "PATCH", body: JSON.stringify(data) });
            modal.close();
            showMessage("Usuario actualizado correctamente.", "success");
            await loadUsers();
          } catch (error) {
            showFieldErrors(form, error);
            showMessage(error.message, "error");
          }
        });
      });
      actionCell.prepend(editButton);
    });
    document.querySelector("#users-filter").addEventListener("submit", async (event) => {
      event.preventDefault();
      usersFilters = Object.fromEntries(new FormData(event.currentTarget));
      await loadUsers(1);
    });
    document.querySelector("#users-prev").addEventListener("click", () => loadUsers(Math.max(1, usersPage - 1)));
    document.querySelector("#users-next").addEventListener("click", () => loadUsers(usersPage + 1));
    document.querySelector("#user-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (!form.reportValidity()) return;
      const data = Object.fromEntries(new FormData(form));
      data.rol = Number(data.rol);
      try {
        await api(endpoints.users, { method: "POST", body: JSON.stringify(data) });
        createModal?.close();
        showMessage("Usuario creado correctamente.", "success");
        await loadUsers();
      } catch (error) {
        showFieldErrors(form, error);
        showMessage(error.message, "error");
      }
    });
    document.querySelectorAll("[data-toggle-user]").forEach((button) => {
      button.addEventListener("click", async () => {
        const estado = button.dataset.state === "ACTIVO" ? "INACTIVO" : "ACTIVO";
        try {
          await api(`${endpoints.users}${button.dataset.toggleUser}/estado/`, {
            method: "PATCH",
            body: JSON.stringify({ estado }),
          });
          showMessage("Estado de usuario actualizado.", "success");
          await loadUsers();
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
    document.querySelectorAll("[data-reset-password]").forEach((button) => {
      button.addEventListener("click", async () => {
        const password = window.prompt("Ingresa la nueva contraseña (mínimo 8 caracteres):");
        if (!password) return;
        try {
          await api(`${endpoints.users}${button.dataset.resetPassword}/restablecer-contrasena/`, {
            method: "POST",
            body: JSON.stringify({ password }),
          });
          showMessage("Contraseña restablecida correctamente.", "success");
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
  }

  async function loadRoles() {
    const [roles, permissions] = await Promise.all([api(endpoints.roles), api(endpoints.permissions)]);
    const permissionModules = Array.isArray(permissions) && permissions[0]?.accion
      ? [...permissions.reduce((groups, permission) => {
        if (!groups.has(permission.modulo)) {
          groups.set(permission.modulo, { modulo: permission.modulo, permisos: [] });
        }
        groups.get(permission.modulo).permisos.push(permission);
        return groups;
      }, new Map()).values()]
      : Array.isArray(permissions)
        ? permissions
        : Object.entries(permissions).map(([modulo, items]) => ({ modulo, permisos: items }));
    const permissionMatrix = permissionModules.map((group) => `
      <section class="permission-module">
        <h3>${escapeHtml(group.modulo)}</h3>
        <div class="permission-grid">${group.permisos.map((permission) => {
          const action = permission.accion;
          const key = `${group.modulo}.${action}`;
          return `<label class="check-row"><input type="checkbox" data-permission="${escapeHtml(key)}" value="${permission.id}"><span><strong>${escapeHtml(action)}</strong><select aria-label="Alcance de ${escapeHtml(key)}" data-scope="${escapeHtml(key)}"><option value="TODOS">Todos</option><option value="A_SU_CARGO">A su cargo</option><option value="PROPIOS">Propios</option></select></span></label>`;
        }).join("")}</div>
      </section>`).join("");
    pageContent.innerHTML = `
      <div class="page-header"><div><p class="eyebrow">Autorización</p><h1>Roles y permisos</h1><p>Configura el acceso que se aplica en la API.</p></div></div>
      <section class="card"><h2 id="role-form-title">Crear rol personalizado</h2>
        <form id="role-form" class="form-stack">
          <input name="id" type="hidden">
          <div class="form-grid"><label>Nombre del rol<input name="nombre" required maxlength="50"></label>
          <label>Estado<select name="estado"><option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></label></div>
          <label>Descripción<textarea name="descripcion"></textarea></label>
          <label>Permisos y alcance</label>
          <div class="permission-matrix">${permissionMatrix}</div>
          <div class="toolbar"><button class="button button-primary">Guardar rol</button><button class="button button-quiet" type="reset">Limpiar</button></div>
        </form>
      </section>
      <section class="section"><h2>Roles actuales</h2><div class="grid-cards">${roles.map((role) =>
        `<article class="card"><h3>${escapeHtml(role.nombre)}</h3><p>${escapeHtml(role.descripcion || "Sin descripción")}</p><p>${role.permisos_configurados.length} permisos · ${escapeHtml(role.estado)}</p>${hasPermission("ROLES", "EDITAR") ? `<button class="button button-quiet" data-edit-role="${role.id}">Editar permisos</button>` : ""}${hasPermission("ROLES", "DESACTIVAR") && !["administrador", "estudiante"].includes(role.nombre.toLowerCase()) ? `<button class="button button-quiet" data-toggle-role="${role.id}" data-state="${escapeHtml(role.estado)}">${role.estado === "ACTIVO" ? "Desactivar" : "Activar"}</button>` : ""}</article>`
      ).join("")}</div></section>`;
    const form = document.querySelector("#role-form");
    form.closest(".card").hidden = !(
      hasPermission("ROLES", "CREAR") || hasPermission("ROLES", "EDITAR")
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      const id = data.id;
      const assignments = [...form.querySelectorAll("[data-permission]:checked")].map((checkbox) => ({
        permiso_id: Number(checkbox.value),
        alcance: form.querySelector(`[data-scope="${CSS.escape(checkbox.dataset.permission)}"]`).value,
      }));
      data.permisos = assignments;
      delete data.id;
      try {
        await api(id ? `${endpoints.roles}${id}/` : endpoints.roles, {
          method: id ? "PUT" : "POST",
          body: JSON.stringify(data),
        });
        showMessage("Rol guardado correctamente.", "success");
        await loadRoles();
      } catch (error) { showMessage(error.message, "error"); }
    });
    document.querySelectorAll("[data-edit-role]").forEach((button) => {
      button.addEventListener("click", () => {
        const role = roles.find((item) => item.id === Number(button.dataset.editRole));
        form.reset();
        form.elements.id.value = role.id;
        form.elements.nombre.value = role.nombre;
        form.elements.nombre.readOnly = ["administrador", "estudiante"].includes(role.nombre.toLowerCase());
        form.elements.descripcion.value = role.descripcion || "";
        form.elements.estado.value = role.estado;
        form.elements.estado.disabled = ["administrador", "estudiante"].includes(role.nombre.toLowerCase());
        role.permisos_configurados.forEach((assignment) => {
          const key = `${assignment.modulo}.${assignment.accion}`;
          const checkbox = form.querySelector(`[data-permission="${CSS.escape(key)}"]`);
          if (checkbox) {
            checkbox.checked = true;
            form.querySelector(`[data-scope="${CSS.escape(key)}"]`).value = assignment.alcance;
          }
        });
        document.querySelectorAll("[data-toggle-role]").forEach((button) => {
          button.addEventListener("click", async () => {
            const estado = button.dataset.state === "ACTIVO" ? "INACTIVO" : "ACTIVO";
            try {
              await api(`${endpoints.roles}${button.dataset.toggleRole}/`, {
                method: "PATCH",
                body: JSON.stringify({ estado }),
              });
              showMessage("Estado del rol actualizado.", "success");
              await loadRoles();
            } catch (error) { showMessage(error.message, "error"); }
          });
        });
        document.querySelector("#role-form-title").textContent = `Editar ${role.nombre}`;
        form.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    form.addEventListener("reset", () => {
      form.elements.id.value = "";
      form.elements.nombre.readOnly = false;
      form.elements.estado.disabled = false;
      document.querySelector("#role-form-title").textContent = "Crear rol personalizado";
    });
  }

  async function loadQuestions() {
    const params = new URLSearchParams({ page: String(questionsPage) });
    Object.entries(questionFilters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const [categories, questionPage] = await Promise.all([
      api(endpoints.categories),
      api(`${endpoints.questions}?${params}`),
    ]);
    const questions = questionPage.results || questionPage;
    pageContent.innerHTML = `
      <div class="page-header"><div><p class="eyebrow">Banco académico</p><h1>Preguntas</h1><p>Organiza categorías y construye preguntas calificables automáticamente.</p></div></div>
      ${hasPermission("CATEGORIAS", "CREAR") || hasPermission("CATEGORIAS", "GESTIONAR") ? `<section class="card"><h2>Nueva categoría</h2><form id="category-form" class="toolbar">
        <input name="nombre" placeholder="Nombre de la categoría" required maxlength="100">
        <input name="descripcion" placeholder="Descripción (opcional)">
        <button class="button button-primary">Crear categoría</button></form></section>` : ""}
      <section class="card section"><h2>Nueva pregunta</h2><form id="question-form" class="form-stack">
        <div class="form-grid"><label>Categoría<select name="categoria" required>${categories.filter((item) => item.estado === "Activo").map((item) => `<option value="${item.id}">${escapeHtml(item.nombre)}</option>`).join("")}</select></label>
        <label>Tipo<select name="tipo"><option value="MULTIPLE">Selección múltiple</option><option value="VERDADERO_FALSO">Verdadero o falso</option></select></label></div>
        <label>Texto base (opcional)<textarea name="texto_base"></textarea></label>
        <label>Enunciado<textarea name="enunciado" required></textarea></label>
        <div class="option-editor">${[1, 2, 3, 4].map((number) => `<div class="option-row"><label>Opción ${number}<input name="opcion_${number}" ${number < 3 ? "required" : ""}><input name="retro_opcion_${number}" placeholder="Retroalimentación de la opción"></label><label class="choice"><input type="radio" name="correcta" value="${number}" ${number === 1 ? "checked" : ""} required> Correcta</label></div>`).join("")}</div>
        <div class="form-grid"><label>Puntaje de referencia<input name="puntaje" type="number" min="0.01" step="0.01" value="1.00" required></label><label>Retroalimentación<textarea name="retroalimentacion"></textarea></label></div>
        <button class="button button-primary">Guardar pregunta</button>
      </form></section>
      <section class="section"><h2>Categorías</h2>${renderTable(
        ["Nombre", "Descripción", "Estado", "Acción"],
        categories.map((category) => `<tr><td>${escapeHtml(category.nombre)}</td><td>${escapeHtml(category.descripcion || "—")}</td><td>${escapeHtml(category.estado)}</td><td>${hasPermission("CATEGORIAS", "EDITAR") || hasPermission("CATEGORIAS", "GESTIONAR") ? `<button class="button button-quiet" data-category="${category.id}" data-state="${escapeHtml(category.estado)}">${category.estado === "Activo" ? "Desactivar" : "Activar"}</button>` : "—"}</td></tr>`)
      )}</section>
      <section class="section"><h2>Banco actual</h2>
      <form id="questions-filter" class="form-grid">
        <label>Buscar texto<input name="search" value="${escapeHtml(questionFilters.search)}" placeholder="Enunciado o texto base"></label>
        <label>Categoría<select name="categoria"><option value="">Todas</option>${categories.map((item) => `<option value="${item.id}" ${String(questionFilters.categoria) === String(item.id) ? "selected" : ""}>${escapeHtml(item.nombre)}</option>`).join("")}</select></label>
        <label>Tipo<select name="tipo"><option value="">Todos</option><option value="MULTIPLE" ${questionFilters.tipo === "MULTIPLE" ? "selected" : ""}>Selección múltiple</option><option value="VERDADERO_FALSO" ${questionFilters.tipo === "VERDADERO_FALSO" ? "selected" : ""}>Verdadero/Falso</option></select></label>
        <label>Estado<select name="estado"><option value="">Todos</option><option value="Activo" ${questionFilters.estado === "Activo" ? "selected" : ""}>Activo</option><option value="Inactivo" ${questionFilters.estado === "Inactivo" ? "selected" : ""}>Inactivo</option></select></label>
        <div class="toolbar"><button class="button button-quiet">Filtrar</button></div>
      </form>${renderTable(
        ["Pregunta", "Categoría", "Tipo", "Opciones", "Estado", "Acción"],
        questions.map((question) => `<tr><td>${escapeHtml(question.enunciado)}</td><td>${escapeHtml(question.categoria_nombre)}</td><td>${escapeHtml(question.tipo)}</td><td>${question.opciones.length}</td><td>${escapeHtml(question.estado)}</td><td>${hasPermission("PREGUNTAS", "EDITAR") ? `<button class="button button-quiet" data-edit-question="${question.id}">Editar</button><button class="button button-quiet" data-question-state="${question.id}" data-state="${escapeHtml(question.estado)}">${question.estado === "Activo" ? "Desactivar" : "Activar"}</button>` : ""}</td></tr>`)
      )}${renderPagination({ page: questionsPage, hasPrevious: Boolean(questionPage.previous), hasNext: Boolean(questionPage.next), previousId: "questions-prev", nextId: "questions-next" })}</section>`;
    document.querySelector("#questions-filter").addEventListener("submit", async (event) => {
      event.preventDefault();
      questionFilters = Object.fromEntries(new FormData(event.currentTarget));
      questionsPage = 1;
      await loadQuestions();
    });
    document.querySelector("#questions-prev").addEventListener("click", async () => {
      questionsPage = Math.max(1, questionsPage - 1);
      await loadQuestions();
    });
    document.querySelector("#questions-next").addEventListener("click", async () => {
      questionsPage += 1;
      await loadQuestions();
    });
    const categoryForm = document.querySelector("#category-form");
    const questionForm = document.querySelector("#question-form");
    if (questionForm) {
      questionForm.closest(".card").hidden = !hasPermission("PREGUNTAS", "CREAR")
        && !hasPermission("PREGUNTAS", "EDITAR");
    }
    categoryForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await api(endpoints.categories, { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(categoryForm))) });
        showMessage("Categoría creada.", "success");
        await loadQuestions();
      } catch (error) { showMessage(error.message, "error"); }
    });
    const categoryRows = [...pageContent.querySelectorAll(".table-wrap")]
      .find((table) => table.closest("section")?.querySelector("h2")?.textContent === "Categorías");
    categoryRows?.querySelectorAll("[data-table-row]").forEach((row, index) => {
      const category = categories[index];
      if (!category || !hasPermission("CATEGORIAS", "EDITAR")) return;
      const editButton = document.createElement("button");
      editButton.type = "button";
      editButton.className = "button button-quiet";
      editButton.textContent = "Editar";
      editButton.addEventListener("click", () => {
        const form = document.createElement("form");
        form.className = "form-stack";
        form.innerHTML = `
          <label>Nombre<input name="nombre" value="${escapeHtml(category.nombre)}" required maxlength="100"></label>
          <label>Descripción<textarea name="descripcion">${escapeHtml(category.descripcion || "")}</textarea></label>
          <div class="toolbar"><button class="button button-primary">Guardar categoría</button></div>`;
        const modal = openModal({ title: "Editar categoría", content: form });
        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          try {
            await api(`${endpoints.categories}${category.id}/`, {
              method: "PATCH",
              body: JSON.stringify(Object.fromEntries(new FormData(form))),
            });
            modal.close();
            showMessage("Categoría actualizada.", "success");
            await loadQuestions();
          } catch (error) {
            showFieldErrors(form, error);
            showMessage(error.message, "error");
          }
        });
      });
      row.lastElementChild.prepend(editButton);
    });
    document.querySelectorAll("[data-category]").forEach((button) => {
      button.addEventListener("click", async () => {
        const estado = button.dataset.state === "Activo" ? "Inactivo" : "Activo";
        try {
          await api(`${endpoints.categories}${button.dataset.category}/`, {
            method: "PATCH", body: JSON.stringify({ estado }),
          });
          showMessage("Categoría actualizada.", "success");
          await loadQuestions();
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
    document.querySelectorAll("[data-question-state]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const estado = button.dataset.state === "Activo" ? "Inactivo" : "Activo";
          await api(`${endpoints.questions}${button.dataset.questionState}/`, {
            method: "PATCH",
            body: JSON.stringify({ estado }),
          });
          showMessage("Estado de la pregunta actualizado.", "success");
          await loadQuestions();
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
    let editingQuestionId = null;
    questionForm.querySelector('[name="tipo"]').addEventListener("change", (event) => {
      const third = questionForm.elements.opcion_3;
      const fourth = questionForm.elements.opcion_4;
      const isTrueFalse = event.target.value === "VERDADERO_FALSO";
      third.required = fourth.required = !isTrueFalse;
      third.readOnly = fourth.readOnly = isTrueFalse;
      if (isTrueFalse) {
        questionForm.elements.opcion_1.value = "Verdadero";
        questionForm.elements.opcion_2.value = "Falso";
        third.value = "";
        fourth.value = "";
      } else {
        questionForm.elements.opcion_1.readOnly = false;
        questionForm.elements.opcion_2.readOnly = false;
      }
    });
    document.querySelectorAll("[data-edit-question]").forEach((button) => {
      button.addEventListener("click", () => {
        const question = questions.find((item) => item.id === Number(button.dataset.editQuestion));
        editingQuestionId = question.id;
        questionForm.elements.categoria.value = question.categoria;
        questionForm.elements.tipo.value = question.tipo;
        questionForm.elements.texto_base.value = question.texto_base || "";
        questionForm.elements.enunciado.value = question.enunciado;
        questionForm.elements.puntaje.value = question.puntaje;
        questionForm.elements.retroalimentacion.value = question.retroalimentacion || "";
        question.opciones.forEach((option, index) => {
          const number = index + 1;
          questionForm.elements[`opcion_${number}`].value = option.texto_opcion;
          questionForm.elements[`retro_opcion_${number}`].value = option.retroalimentacion || "";
          questionForm.querySelector(`[name="correcta"][value="${number}"]`).checked = option.es_correcta;
        });
        questionForm.elements.tipo.dispatchEvent(new Event("change"));
        questionForm.querySelector("button[type='submit'],button:not([type])").textContent = "Actualizar pregunta";
        questionForm.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    questionForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(questionForm));
      const options = [1, 2, 3, 4]
        .map((number) => ({ number, text: data[`opcion_${number}`]?.trim() }))
        .filter((option) => option.text)
        .map((option) => ({
          texto_opcion: option.text,
          es_correcta: option.number === Number(data.correcta),
          retroalimentacion: data[`retro_opcion_${option.number}`] || "",
        }));
      data.categoria = Number(data.categoria);
      data.opciones = options;
      delete data.correcta;
      [1, 2, 3, 4].forEach((number) => {
        delete data[`opcion_${number}`];
        delete data[`retro_opcion_${number}`];
      });
      try {
        await api(editingQuestionId ? `${endpoints.questions}${editingQuestionId}/` : endpoints.questions, {
          method: editingQuestionId ? "PATCH" : "POST",
          body: JSON.stringify(data),
        });
        showMessage(editingQuestionId ? "Pregunta actualizada correctamente." : "Pregunta creada correctamente.", "success");
        editingQuestionId = null;
        await loadQuestions();
      } catch (error) {
        showFieldErrors(questionForm, error);
        showMessage(error.message, "error");
      }
    });
  }

  async function loadQuizzes() {
    const canConfigure = hasPermission("CUESTIONARIOS", "CREAR")
      || hasPermission("CUESTIONARIOS", "EDITAR")
      || hasPermission("CUESTIONARIOS", "GESTIONAR");
    const [quizzes, questions] = await Promise.all([
      api(endpoints.quizzes),
      canConfigure ? fetchAllPages(endpoints.questions, { estado: "Activo" }) : Promise.resolve([]),
    ]);
    pageContent.innerHTML = `
      <div class="page-header"><div><p class="eyebrow">Evaluaciones</p><h1>Cuestionarios</h1><p>Programa pruebas y define su calificación e intentos.</p></div></div>
      <section class="card"><h2>Configurar cuestionario</h2><form id="quiz-form" class="form-stack">
        <div class="form-grid"><label>Nombre<input name="nombre" required maxlength="150"></label><label>Estado<select name="estado"><option value="BORRADOR">Borrador</option><option value="PROGRAMADO">Programado</option><option value="DISPONIBLE">Disponible</option><option value="CERRADO">Cerrado</option></select></label></div>
        <label>Descripción<textarea name="descripcion"></textarea></label>
        <div class="form-grid"><label>Apertura<input name="fecha_apertura" type="datetime-local" required></label><label>Cierre<input name="fecha_cierre" type="datetime-local" required></label></div>
        <div class="form-grid"><label>Tiempo límite (minutos)<input name="tiempo_limite_minutos" type="number" min="1" value="60" required></label><label>Intentos permitidos<input name="intentos_permitidos" type="number" min="1" value="1" required></label></div>
        <div class="form-grid"><label>Calificación máxima<input name="calificacion_maxima" type="number" min="0.01" step="0.01" value="5.00" required></label><label>Calificación de aprobación<input name="calificacion_aprobacion" type="number" min="0" step="0.01" value="3.00" required></label></div>
        <div class="check-grid"><label class="check-row"><input name="mezclar_preguntas" type="checkbox" checked> Mezclar preguntas</label><label class="check-row"><input name="mezclar_respuestas" type="checkbox" checked> Mezclar respuestas</label><label class="check-row"><input name="permitir_revision" type="checkbox" checked> Permitir revisión al finalizar</label></div>
        <h3>Preguntas, orden y puntaje</h3><div class="check-grid">${questions.filter((item) => item.estado === "Activo").map((question, index) => `<div class="check-row"><input type="checkbox" data-question="${question.id}"><span>${escapeHtml(question.enunciado)} <span class="question-config"><label>Orden<input data-order="${question.id}" type="number" min="1" value="${index + 1}" aria-label="Orden de la pregunta"></label><label>Puntaje<input data-score="${question.id}" type="number" min="0.01" step="0.01" value="${escapeHtml(question.puntaje)}" aria-label="Puntaje"></label></span></span></div>`).join("")}</div>
        <button class="button button-primary">Guardar cuestionario</button>
      </form></section>
      <section class="section"><h2>Cuestionarios creados</h2>${renderTable(
        ["Nombre", "Apertura", "Cierre", "Estado", "Preguntas", "Acciones"],
        quizzes.map((quiz) => `<tr><td>${escapeHtml(quiz.nombre)}</td><td>${formatDateTime(quiz.fecha_apertura)}</td><td>${formatDateTime(quiz.fecha_cierre)}</td><td><span class="badge">${escapeHtml(quiz.estado_efectivo || quiz.estado)}</span></td><td>${quiz.preguntas.length}</td><td>${hasPermission("CUESTIONARIOS", "EDITAR") ? `<button class="button button-quiet" data-edit-quiz="${quiz.id}">Editar</button>` : ""}${hasPermission("CUESTIONARIOS", "EDITAR") ? `<button class="button button-quiet" data-publish-quiz="${quiz.id}">Publicar</button>` : ""}${hasPermission("CUESTIONARIOS", "DESACTIVAR") ? `<button class="button button-quiet" data-disable-quiz="${quiz.id}">Desactivar</button>` : ""}</td></tr>`)
      )}</section>`;
    const form = document.querySelector("#quiz-form");
    form.closest(".card").hidden = !canConfigure;
    let editingQuizId = null;
    const fields = [
      "nombre", "descripcion", "fecha_apertura", "fecha_cierre",
      "tiempo_limite_minutos", "intentos_permitidos", "calificacion_maxima",
      "calificacion_aprobacion",
    ];
    const dateForInput = (value) => {
      const date = new Date(value);
      date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
      return date.toISOString().slice(0, 16);
    };
    document.querySelectorAll("[data-edit-quiz]").forEach((button) => {
      button.addEventListener("click", () => {
        const quiz = quizzes.find((item) => item.id === Number(button.dataset.editQuiz));
        editingQuizId = quiz.id;
        fields.forEach((field) => {
          form.elements[field].value = field.startsWith("fecha_")
            ? dateForInput(quiz[field])
            : quiz[field] ?? "";
        });
        form.elements.estado.value = quiz.estado;
        ["mezclar_preguntas", "mezclar_respuestas", "permitir_revision"].forEach((field) => {
          form.elements[field].checked = quiz[field];
        });
        quiz.preguntas.forEach((relation) => {
          const id = relation.pregunta;
          const checkbox = form.querySelector(`[data-question="${id}"]`);
          if (!checkbox) return;
          checkbox.checked = true;
          form.querySelector(`[data-order="${id}"]`).value = relation.orden;
          form.querySelector(`[data-score="${id}"]`).value = relation.puntaje;
        });
        form.querySelector("button[type='submit'],button:not([type])").textContent = "Actualizar cuestionario";
        form.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    document.querySelectorAll("[data-publish-quiz]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await api(`${endpoints.quizzes}${button.dataset.publishQuiz}/publicar/`, {
            method: "POST",
            body: JSON.stringify({}),
          });
          showMessage("Cuestionario publicado.", "success");
          await loadQuizzes();
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
    document.querySelectorAll("[data-disable-quiz]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await api(`${endpoints.quizzes}${button.dataset.disableQuiz}/desactivar/`, {
            method: "POST",
            body: JSON.stringify({}),
          });
          showMessage("Cuestionario desactivado.", "success");
          await loadQuizzes();
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      ["mezclar_preguntas", "mezclar_respuestas", "permitir_revision"].forEach((field) => {
        data[field] = form.elements[field].checked;
      });
      ["tiempo_limite_minutos", "intentos_permitidos"].forEach((field) => { data[field] = Number(data[field]); });
      ["calificacion_maxima", "calificacion_aprobacion"].forEach((field) => { data[field] = Number(data[field]); });
      data.fecha_apertura = new Date(data.fecha_apertura).toISOString();
      data.fecha_cierre = new Date(data.fecha_cierre).toISOString();
      data.preguntas = [...form.querySelectorAll("[data-question]:checked")]
        .sort((first, second) =>
          Number(form.querySelector(`[data-order="${first.dataset.question}"]`).value)
          - Number(form.querySelector(`[data-order="${second.dataset.question}"]`).value)
        ).map((checkbox, index) => ({
        pregunta: Number(checkbox.dataset.question),
        orden: Number(form.querySelector(`[data-order="${checkbox.dataset.question}"]`).value) || index + 1,
        puntaje: Number(form.querySelector(`[data-score="${checkbox.dataset.question}"]`).value),
      }));
      try {
        await api(editingQuizId ? `${endpoints.quizzes}${editingQuizId}/` : endpoints.quizzes, {
          method: editingQuizId ? "PATCH" : "POST",
          body: JSON.stringify(data),
        });
        showMessage(editingQuizId ? "Cuestionario actualizado." : "Cuestionario creado.", "success");
        editingQuizId = null;
        await loadQuizzes();
      } catch (error) {
        showFieldErrors(form, error);
        showMessage(error.message, "error");
      }
    });
  }

  async function loadImports() {
    const canImport = hasPermission("IMPORTACIONES", "IMPORTAR")
      || hasPermission("IMPORTACION", "IMPORTAR");
    const canViewHistory = hasPermission("IMPORTACIONES", "VER");
    const [history, quizzes] = await Promise.all([
      canViewHistory ? api(endpoints.history) : Promise.resolve([]),
      canImport ? api(endpoints.quizzes) : Promise.resolve([]),
    ]);
    pageContent.innerHTML = `
      <div class="page-header"><div><p class="eyebrow">Carga masiva</p><h1>Importar preguntas desde Excel</h1><p>Descarga la plantilla, revisa las filas y confirma la importación cuando estés listo. Puedes importar solo al banco o añadir preguntas a un cuestionario sin intentos. Las preguntas ya existentes se cuentan como duplicadas, no como errores.</p></div>${canImport ? `<button id="download-import-template" class="button button-quiet" type="button">Descargar plantilla .xlsx</button>` : ""}</div>
      ${canImport ? `<section class="card"><form id="import-form" class="form-stack">
        <label>Destino de las preguntas<select name="cuestionario_id"><option value="">Solo banco de preguntas</option>${quizzes.map((quiz) => `<option value="${quiz.id}">${escapeHtml(quiz.nombre)}</option>`).join("")}</select></label>
        <label>Libro Excel (.xlsx)<input class="file-input" name="archivo" type="file" accept=".xlsx" required></label>
        <div class="toolbar"><button class="button button-primary">Previsualizar filas</button><button id="confirm-import" class="button button-primary" type="button" hidden>Confirmar importación</button></div>
      </form><div id="import-preview"></div></section>` : ""}
      ${canViewHistory ? `<section class="section"><h2>Historial de importaciones</h2>
        <div class="toolbar"><button id="export-import-history" class="button button-quiet" type="button">Exportar vista a Excel</button></div>
        <div class="history-tabs" role="tablist">
          <button type="button" class="history-tab active" data-history-filter="all" role="tab" aria-selected="true">Todas</button>
          <button type="button" class="history-tab" data-history-filter="validas" role="tab" aria-selected="false">Válidas</button>
          <button type="button" class="history-tab" data-history-filter="duplicadas" role="tab" aria-selected="false">Duplicadas</button>
          <button type="button" class="history-tab" data-history-filter="errores" role="tab" aria-selected="false">Con errores</button>
        </div>
        ${renderTable(
          ["Archivo", "Fecha", "Nuevas", "Duplicadas", "Con errores", "Resultado", "Detalle"],
          history.map((item) => {
            const { date, time } = formatDateParts(item.fecha_importacion);
            return `
              <tr data-table-row data-history-kinds="${getImportHistoryKinds(item)}">
                <td class="filename-cell" title="${escapeHtml(item.nombre_archivo || "")}">
                  <span class="filename-text">${escapeHtml(item.nombre_archivo)}</span>
                </td>
                <td class="date-cell" title="${escapeHtml(`${date} ${time}`)}">
                  <span class="date-text">${date}</span>
                  <span class="time-text">${time}</span>
                </td>
                <td>${item.registros_exitosos}</td>
                <td>${item.registros_duplicados}</td>
                <td>${item.registros_con_errores}</td>
                <td>${escapeHtml(item.estado_resultado)}</td>
                <td class="import-detail-cell">
                  <details class="import-detail">
                    <summary>Ver detalle</summary>
                    <div class="import-detail-content">${formatImportDetail(item.detalles_error)}</div>
                  </details>
                </td>
              </tr>`;
          })
        )}
      </section>` : ""}`;

    document.querySelectorAll("[data-history-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        const selected = button.dataset.historyFilter;
        document.querySelectorAll("[data-history-filter]").forEach((tab) => {
          const active = tab === button;
          tab.classList.toggle("active", active);
          tab.setAttribute("aria-selected", String(active));
        });
        const historyTable = document.querySelector(".table-search")?.nextElementSibling;
        if (historyTable) historyTable.dataset.historyFilter = selected;
        const searchTerm = document.querySelector("[data-table-search]")
          ?.value.trim().toLocaleLowerCase() || "";
        document.querySelectorAll("[data-table-row]").forEach((row) => {
          const matchesCategory = selected === "all"
            || row.dataset.historyKinds.split(" ").includes(selected);
          const rowText = (row.dataset.tableSearchText || row.textContent).toLocaleLowerCase();
          row.hidden = !matchesCategory || !rowText.includes(searchTerm);
        });
      });
    });
    const exportHistoryButton = document.querySelector("#export-import-history");
    if (exportHistoryButton) {
      exportHistoryButton.addEventListener("click", async () => {
        const selected = document.querySelector("[data-history-filter].active")
          ?.dataset.historyFilter || "all";
        try {
          const workbook = await api(`${endpoints.history}exportar/?tipo=${encodeURIComponent(selected)}`);
          const url = URL.createObjectURL(workbook);
          const link = document.createElement("a");
          link.href = url;
          link.download = `historial_importaciones_${selected}.xlsx`;
          link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (error) { showMessage(error.message, "error"); }
      });
    }
    const formElement = document.querySelector("#import-form");
    if (!formElement) return;
    const confirmButton = document.querySelector("#confirm-import");
    const previewContainer = document.querySelector("#import-preview");
    let previsualizacion = null;
    let previewFingerprint = "";
    const fingerprint = () => {
      const file = formElement.elements.archivo.files[0];
      return file
        ? `${formElement.elements.cuestionario_id.value}:${file.name}:${file.size}:${file.lastModified}`
        : "";
    };
    const clearPreview = () => {
      previsualizacion = null;
      previewFingerprint = "";
      confirmButton.hidden = true;
      previewContainer.replaceChildren();
    };
    formElement.elements.archivo.addEventListener("change", clearPreview);
    formElement.elements.cuestionario_id.addEventListener("change", clearPreview);
    document.querySelector("#download-import-template").addEventListener("click", async () => {
      try {
        const workbook = await api(`${endpoints.imports}plantilla/`);
        const url = URL.createObjectURL(workbook);
        const link = document.createElement("a");
        link.href = url;
        link.download = "plantilla_preguntas_saber_tyt.xlsx";
        link.click();
        URL.revokeObjectURL(url);
      } catch (error) { showMessage(error.message, "error"); }
    });
    formElement.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        previsualizacion = await api(`${endpoints.imports}previsualizar/`, {
          method: "POST",
          body: new FormData(formElement),
        });
        previewFingerprint = fingerprint();
        previewContainer.innerHTML = `
          <h2>Resultado de la previsualización (${previsualizacion.total_registros} filas)</h2>
          <p>${previsualizacion.validas.length} válidas · ${previsualizacion.duplicadas.length} duplicadas · ${previsualizacion.errores.length} con errores</p>
          ${!formElement.elements.cuestionario_id.value ? '<p class="form-hint">Las preguntas se guardarán únicamente en el banco y no se añadirán a ningún cuestionario.</p>' : ""}
          ${!previsualizacion.validas.length ? '<p class="form-hint">No hay preguntas nuevas para crear en el banco. Al confirmar, las preguntas duplicadas solo se añadirán si todavía no están vinculadas al cuestionario. Revisa la pestaña «Con errores» y corrige esas filas en el Excel.</p>' : ""}
          <div class="preview-tabs" role="tablist">${["validas", "duplicadas", "errores"].map((key, index) => `<button class="button button-quiet ${index === 0 ? "active" : ""}" type="button" role="tab" aria-selected="${index === 0}" aria-controls="preview-${key}" data-preview-tab="${key}">${key === "validas" ? "Válidas" : key === "duplicadas" ? "Duplicadas" : "Con errores"} (${previsualizacion[key].length})</button>`).join("")}</div>
          ${["validas", "duplicadas", "errores"].map((key, index) => `<section id="preview-${key}" role="tabpanel" class="preview-panel ${index ? "hidden" : ""}" data-preview-panel="${key}"><ul>${previsualizacion[key].map((item) => `<li><strong>Fila ${item.fila}:</strong> ${escapeHtml(item.motivo || item.datos?.enunciado || "Registro repetido")}${item.categoria ? ` · Categoría ${escapeHtml(item.categoria.estado)}` : ""}</li>`).join("") || "<li>Sin filas en esta categoría.</li>"}</ul></section>`).join("")}`;
        previewContainer.querySelectorAll("[data-preview-tab]").forEach((tab) => {
          tab.addEventListener("click", () => {
            previewContainer.querySelectorAll("[data-preview-tab]").forEach((item) => {
              const selected = item === tab;
              item.classList.toggle("active", selected);
              item.setAttribute("aria-selected", String(selected));
            });
            previewContainer.querySelectorAll("[data-preview-panel]").forEach((panel) => {
              panel.classList.toggle("hidden", panel.dataset.previewPanel !== tab.dataset.previewTab);
            });
          });
        });
        confirmButton.hidden = false;
        showMessage("Previsualización terminada; todavía no se guardó ninguna fila.", "success");
      } catch (error) { showMessage(error.message, "error"); }
    });
    confirmButton.addEventListener("click", async () => {
      if (!previsualizacion || previewFingerprint !== fingerprint()) {
        showMessage("Vuelve a previsualizar: el archivo cambió desde la validación.", "error");
        confirmButton.hidden = true;
        return;
      }
      try {
        const result = await api(`${endpoints.imports}confirmar/`, {
          method: "POST",
          body: new FormData(formElement),
        });
        const agregadas = Number(result.preguntas_agregadas_cuestionario || 0);
        let mensaje;
        if (result.importacion.cuestionario) {
          mensaje = agregadas
            ? `Se agregaron ${agregadas} preguntas al cuestionario (${result.importacion.registros_exitosos} nuevas en el banco). ${result.importacion.registros_duplicados} duplicadas y ${result.importacion.registros_con_errores} con errores.`
            : `No se agregó ninguna pregunta al cuestionario: ${result.importacion.registros_duplicados} filas ya son duplicadas y ${result.importacion.registros_con_errores} tienen errores. Corrige los errores y carga preguntas nuevas o selecciona un cuestionario donde las duplicadas aún no estén vinculadas.`;
        } else {
          mensaje = `Se importaron ${result.importacion.registros_exitosos} preguntas nuevas al banco. ${result.importacion.registros_duplicados} duplicadas y ${result.importacion.registros_con_errores} con errores.`;
        }
        showMessage(mensaje, result.importacion.registros_con_errores ? "error" : "success");
        await loadImports();
      } catch (error) { showMessage(error.message, "error"); }
    });
  }

  async function loadConfig() {
    const config = await api(endpoints.config);
    pageContent.innerHTML = `
      <div class="page-header"><div><p class="eyebrow">Administración</p><h1>Configuración institucional</h1><p>Personaliza la identidad y los canales de contacto.</p></div></div>
      <section class="card"><form id="config-form" class="form-stack">
        <div class="form-grid"><label>Nombre del sistema<input name="nombre_sistema" value="${escapeHtml(config.nombre_sistema)}" required maxlength="150"></label>
        <label>Institución<input name="institucion" value="${escapeHtml(config.institucion)}" required maxlength="150"></label>
        <label>Zona horaria<input name="zona_horaria" value="${escapeHtml(config.zona_horaria)}" required maxlength="50"></label>
        <label>Correo de contacto<input name="correo_contacto" type="email" value="${escapeHtml(config.correo_contacto || "")}"></label>
        <label>Teléfono de contacto<input name="telefono_contacto" value="${escapeHtml(config.telefono_contacto || "")}" maxlength="20"></label>
        <label>Ruta del logo<input name="logo" value="${escapeHtml(config.logo || "")}" maxlength="255"></label></div>
        <button class="button button-primary">Guardar configuración</button>
      </form></section>`;
    document.querySelector("#config-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await api(endpoints.config, {
          method: "PATCH",
          body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))),
        });
        showMessage("Configuración guardada.", "success");
      } catch (error) { showMessage(error.message, "error"); }
    });
  }

  async function loadAvailable() {
    const quizzes = await api(endpoints.available);
    pageContent.innerHTML = `<div class="page-header"><div><p class="eyebrow">Práctica</p><h1>Cuestionarios disponibles</h1><p>Al iniciar se reservará uno de tus intentos.</p></div></div>
      ${quizzes.length ? `<div class="grid-cards">${quizzes.map((quiz) => `<article class="card"><span class="badge">${quiz.preguntas.length} preguntas</span><h2>${escapeHtml(quiz.nombre)}</h2><p>${escapeHtml(quiz.descripcion || "Sin descripción")}</p><p>${quiz.tiempo_limite_minutos} min · ${quiz.intentos_restantes} intentos restantes de ${quiz.intentos_permitidos} · Nota máxima ${quiz.calificacion_maxima}</p><button class="button button-primary" data-start="${quiz.id}" ${quiz.intentos_restantes < 1 ? "disabled" : ""}>${quiz.intentos_restantes < 1 ? "Sin intentos restantes" : "Iniciar prueba"}</button></article>`).join("")}</div>` : '<div class="empty">No hay cuestionarios abiertos en este momento.</div>'}`;
    document.querySelectorAll("[data-start]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const attempt = await api(`/api/cuestionarios/${button.dataset.start}/intentos/iniciar/`, { method: "POST", body: JSON.stringify({}) });
          renderAttempt(attempt);
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
  }

  function renderAttempt(attempt) {
    activePage = "attempt";
    const questionsHtml = attempt.preguntas.map((question, index) => `
      <article class="question-card">
        <p class="eyebrow">Pregunta ${index + 1} · ${escapeHtml(question.puntaje)} puntos</p>
        ${question.texto_base ? `<p class="muted">${escapeHtml(question.texto_base)}</p>` : ""}
        <h2>${escapeHtml(question.enunciado)}</h2>
        <div>${question.opciones.map((option) => `<label class="choice"><input type="radio" name="answer-${question.id}" value="${option.id}" ${question.opcion_seleccionada_id === option.id ? "checked" : ""}><span>${escapeHtml(option.texto_opcion)}</span></label>`).join("")}</div>
        <label class="check-row"><input type="checkbox" data-review="${question.id}" ${question.marcada_para_revision ? "checked" : ""}> Marcar para revisar</label>
      </article>`).join("");
    pageContent.innerHTML = `<div class="page-header"><div><p class="eyebrow">Intento en curso</p><h1>${escapeHtml(attempt.cuestionario_nombre)}</h1><p id="timer" data-deadline="${escapeHtml(attempt.fecha_limite)}"></p></div><span class="badge">${escapeHtml(attempt.estado)}</span></div>
      <div id="exam-questions">${questionsHtml}</div><button id="submit-attempt" class="button button-primary">Enviar respuestas y calificar</button>`;
    pageContent.querySelectorAll('input[type="radio"]').forEach((input) => input.addEventListener("change", () => {
      const questionId = Number(input.name.replace("answer-", ""));
      saveAttemptAnswer(attempt.id, questionId, Number(input.value));
    }));
    pageContent.querySelectorAll("[data-review]").forEach((input) => input.addEventListener("change", () => {
      saveAttemptAnswer(attempt.id, Number(input.dataset.review), undefined, input.checked);
    }));
    document.querySelector("#submit-attempt").dataset.attemptId = attempt.id;
    document.querySelector("#submit-attempt").addEventListener("click", () => sendAttempt(attempt.id));
    startTimer();
  }

  async function sendAttempt(attemptId, automatic = false) {
    if (!automatic && !window.confirm("¿Enviar el intento? Las preguntas sin responder se calificarán con cero.")) return;
    try {
      await answerQueue;
      const result = await api(`/api/intentos/${attemptId}/finalizar/`, { method: "POST", body: JSON.stringify({}) });
      renderAttemptResult(result);
    } catch (error) {
      showMessage(`No se pudo guardar una respuesta pendiente: ${error.message}`, "error");
    }
  }

  async function saveAttemptAnswer(attemptId, questionId, optionId, marked) {
    const body = { pregunta_id: questionId };
    if (optionId !== undefined) body.opcion_seleccionada_id = optionId;
    if (marked !== undefined) body.marcada_para_revision = marked;
    answerQueue = answerQueue.catch(() => {}).then(() =>
      api(`/api/intentos/${attemptId}/respuestas/`, { method: "PUT", body: JSON.stringify(body) })
    );
    answerQueue.catch((error) => showMessage(error.message, "error"));
    return answerQueue;
  }

  function startTimer() {
    const timer = document.querySelector("#timer");
    if (!timer) return;
    const tick = () => {
      const remaining = Math.max(0, Math.floor((new Date(timer.dataset.deadline) - Date.now()) / 1000));
      timer.textContent = `Tiempo restante: ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`;
      if (remaining <= 0) {
        const submit = document.querySelector("#submit-attempt");
        if (submit) sendAttempt(submit.dataset.attemptId, true);
      } else {
        window.setTimeout(tick, 1000);
      }
    };
    tick();
  }

  function renderAttemptResult(attempt) {
    pageContent.innerHTML = `<div class="page-header"><div><p class="eyebrow">Resultado</p><h1>${escapeHtml(attempt.cuestionario_nombre)}</h1><p>Intento ${attempt.numero_intento} · ${escapeHtml(attempt.estado)} · ${attempt.aprobado ? "Aprobado" : "No aprobado"}</p></div><span class="score">${escapeHtml(attempt.calificacion_final)} / ${escapeHtml(attempt.calificacion_maxima)}</span></div>
      ${attempt.revision_disponible ? attempt.preguntas.map((question, index) => `<article class="question-card"><p class="eyebrow">Pregunta ${index + 1} · ${question.es_correcta ? "Correcta" : "Incorrecta o sin responder"}</p><h2>${escapeHtml(question.enunciado)}</h2>${question.opciones.map((option) => `<p class="choice">${option.es_correcta ? "✓" : "○"} ${escapeHtml(option.texto_opcion)}${option.id === question.opcion_seleccionada_id ? " · Tu respuesta" : ""}</p>`).join("")}${question.retroalimentacion ? `<p class="muted">${escapeHtml(question.retroalimentacion)}</p>` : ""}</article>`).join("") : '<div class="empty">La revisión detallada no está habilitada para este cuestionario.</div>'}
      <button class="button button-quiet" data-page="results">Ver resultados</button>`;
    pageContent.querySelector("[data-page='results']")?.addEventListener("click", () => loadPage("results"));
  }

  async function loadResults() {
    const ownResults = profile?.rol?.toLowerCase() === "estudiante"
      || (!hasPermission("RESULTADOS", "VER")
        && hasPermission("RESULTADOS", "VER_PROPIA_NOTA"));
    const params = new URLSearchParams(
      Object.entries(resultsFilters).filter(([, value]) => Boolean(value))
    );
    const resultData = await api(ownResults ? "/api/intentos/mis-resultados/" : `${endpoints.results}?${params}`);
    const results = resultData.results || resultData;
    const quizzes = ownResults ? [] : [
      ...new Map(results.map((item) => [
        item.cuestionario,
        { id: item.cuestionario, nombre: item.cuestionario_nombre },
      ])).values(),
    ];
    const users = ownResults ? [] : [
      ...new Map(results.map((item) => [
        item.usuario,
        { id: item.usuario, nombre: item.usuario_nombre, codigo: `ID ${item.usuario}` },
      ])).values(),
    ];
    if (
      !ownResults
      && resultsFilters.usuario_id
      && !users.some((user) => String(user.id) === String(resultsFilters.usuario_id))
    ) {
      users.push({
        id: resultsFilters.usuario_id,
        nombre: "Estudiante filtrado",
        codigo: `ID ${resultsFilters.usuario_id}`,
      });
    }
    if (
      !ownResults
      && resultsFilters.cuestionario_id
      && !quizzes.some((quiz) => String(quiz.id) === String(resultsFilters.cuestionario_id))
    ) {
      quizzes.push({ id: resultsFilters.cuestionario_id, nombre: "Cuestionario filtrado" });
    }
    pageContent.innerHTML = `<div class="page-header"><div><p class="eyebrow">Seguimiento</p><h1>Resultados</h1><p>Consulta notas, estado de aprobación y duración de los intentos.</p></div></div>
      ${!ownResults ? `<section class="card"><form id="results-filter" class="form-grid">
        <label>Cuestionario<select name="cuestionario_id"><option value="">Todos los cuestionarios</option>${quizzes.map((quiz) => `<option value="${quiz.id}" ${String(resultsFilters.cuestionario_id) === String(quiz.id) ? "selected" : ""}>${escapeHtml(quiz.nombre)}</option>`).join("")}</select></label>
        <label>Estudiante<select name="usuario_id"><option value="">Todos los estudiantes</option>${users.map((user) => `<option value="${user.id}" ${String(resultsFilters.usuario_id) === String(user.id) ? "selected" : ""}>${escapeHtml(user.nombre)} · ${escapeHtml(user.codigo)}</option>`).join("")}</select></label>
        <div class="toolbar"><button class="button button-quiet">Filtrar resultados</button></div>
      </form></section>` : ""}
      ${renderTable(
      ["Cuestionario", "Estudiante", "Intento", "Puntaje", "Calificación", "Aprobación", "Duración", "Estado", "Fecha", "Detalle"],
      results.map((item) => `<tr><td>${escapeHtml(item.cuestionario_nombre)}</td><td>${escapeHtml(item.usuario_nombre)}</td><td>${item.numero_intento}</td><td>${escapeHtml(item.puntaje_obtenido ?? "En curso")}</td><td>${escapeHtml(item.calificacion_final ?? "—")}</td><td>${item.aprobado === null || item.aprobado === undefined ? "Pendiente" : item.aprobado ? "Aprobado" : "Reprobado"}</td><td>${item.duracion_segundos == null ? "—" : `${Math.floor(item.duracion_segundos / 60)} min ${item.duracion_segundos % 60} s`}</td><td>${escapeHtml(item.estado)}</td><td>${formatDateTime(item.fecha_inicio)}</td><td>${item.calificacion_final == null ? "—" : `<button class="button button-quiet" data-result="${item.id}">Revisar</button>`}</td></tr>`)
    )}`;
    pageContent.querySelector("#results-filter")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      resultsFilters = Object.fromEntries(new FormData(event.currentTarget));
      await loadResults();
    });
    pageContent.querySelectorAll("[data-result]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          const attempt = await api(`/api/resultados/${button.dataset.result}/`);
          renderAttemptResult(attempt);
        } catch (error) { showMessage(error.message, "error"); }
      });
    });
  }

  function permissionForPage(page) {
    const pagePermissions = {
      users: ["USUARIOS.VER", "USUARIOS.CREAR", "USUARIOS.EDITAR", "USUARIOS.DESACTIVAR"]
        .find((permission) => hasPermission(permission)) || "USUARIOS.VER",
      roles: ["ROLES.VER", "ROLES.CREAR", "ROLES.EDITAR", "ROLES.DESACTIVAR"]
        .find((permission) => hasPermission(permission)) || "ROLES.VER",
      questions: [
        "PREGUNTAS.VER", "CATEGORIAS.VER", "PREGUNTAS.CREAR",
        "PREGUNTAS.EDITAR", "PREGUNTAS.DESACTIVAR",
        "CATEGORIAS.CREAR", "CATEGORIAS.EDITAR", "CATEGORIAS.DESACTIVAR",
      ].find((permission) => hasPermission(permission)) || "PREGUNTAS.VER",
      quizzes: ["CUESTIONARIOS.VER", "CUESTIONARIOS.CREAR", "CUESTIONARIOS.EDITAR", "CUESTIONARIOS.DESACTIVAR"]
        .find((permission) => hasPermission(permission)) || "CUESTIONARIOS.VER",
      imports: [
        "IMPORTACIONES.VER", "IMPORTACIONES.IMPORTAR", "IMPORTACION.IMPORTAR",
        "IMPORTACIONES.CREAR",
      ].find((permission) => hasPermission(permission)) || "IMPORTACIONES.IMPORTAR",
      config: "CONFIGURACION.EDITAR",
      available: "CUESTIONARIOS.VER_DISPONIBLES",
      results: profile?.rol?.toLowerCase() === "estudiante"
        ? "RESULTADOS.VER_PROPIA_NOTA"
        : "RESULTADOS.VER",
      reports: "REPORTES.VER",
    };
    return pagePermissions[page];
  }

  async function loadPage(page) {
    const requiredPermission = permissionForPage(page);
    if (!guard({ permission: requiredPermission })) return;
    activePage = page;
    buildNavigation();
    showMessage("");
    try {
      if (page === "home") renderHome();
      else if (page === "users") await loadUsers();
      else if (page === "roles") await loadRoles();
      else if (page === "questions") await loadQuestions();
      else if (page === "quizzes") await loadQuizzes();
      else if (page === "imports") await loadImports();
      else if (page === "config") await loadConfig();
      else if (page === "available") await loadAvailable();
      else if (page === "results") await loadResults();
      else if (page === "reports") window.location.assign("/reportes/");
    } catch (error) {
      pageContent.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      showMessage("No fue posible cargar esta sección.", "error");
    }
  }

  async function enterDashboard() {
    profile = await getCurrentUser(true);
    if (!profile) return;
    accountName.textContent = `${profile.nombre} · ${profile.rol}`;
    loginView.classList.add("hidden");
    dashboardView.classList.remove("hidden");
    logoutButton.classList.remove("hidden");
    await loadPage("home");
  }

  initializeFormValidation();
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginMessage.textContent = "";
    const credentials = Object.fromEntries(new FormData(loginForm));
    if (!credentials.codigo.trim() && !credentials.correo.trim()) {
      loginMessage.textContent = "Ingresa tu código o correo electrónico.";
      loginMessage.className = "message error";
      loginForm.elements.codigo.classList.add("is-invalid");
      loginForm.elements.correo.classList.add("is-invalid");
      return;
    }
    const submit = loginForm.querySelector("[type=submit]");
    submit.disabled = true;
    submit.classList.add("is-loading");
    try {
      await authenticate(credentials);
      await enterDashboard();
    } catch (error) {
      loginMessage.textContent = error.message;
      loginMessage.className = "message error";
      showToast(error.message, "error");
    } finally {
      submit.disabled = false;
      submit.classList.remove("is-loading");
    }
  });

  logoutButton.addEventListener("click", async () => {
    logoutButton.disabled = true;
    try {
      await endSession();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      profile = null;
      accountName.textContent = "";
      logoutButton.classList.add("hidden");
      logoutButton.disabled = false;
      dashboardView.classList.add("hidden");
      loginView.classList.remove("hidden");
      pageContent.replaceChildren();
      loginForm.reset();
    }
  });

  if (sessionStorage.getItem("tyt_access")) {
    enterDashboard().catch((error) => {
      showToast(error.message, "error");
    });
  }
})();
