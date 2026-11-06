export function renderTable(headers, rows, { searchable = true } = {}) {
  if (!rows.length) return '<div class="empty">No hay registros para mostrar.</div>';
  const search = searchable
    ? '<label class="table-search">Buscar en esta tabla<input type="search" data-table-search placeholder="Escribe para filtrar resultados"></label>'
    : "";
  const headersText = headers.join(" ");
  const taggedRows = rows.map((row) => {
    const plainText = row.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
    return row.replace(
      "<tr>",
      `<tr data-table-row data-table-search-text="${escapeHtml(`${headersText} ${plainText}`)}">`
    );
  });
  return `${search}<div class="table-wrap"><table><thead><tr>${headers.map((item) => `<th>${escapeHtml(item)}</th>`).join("")}</tr></thead><tbody>${taggedRows.join("")}</tbody></table></div>`;
}

export function renderPagination({ page, hasPrevious, hasNext, previousId, nextId }) {
  return `<div class="toolbar pagination">
    <button class="button button-quiet" type="button" id="${escapeHtml(previousId)}" ${hasPrevious ? "" : "disabled"}>Anterior</button>
    <span>Página ${page}</span>
    <button class="button button-quiet" type="button" id="${escapeHtml(nextId)}" ${hasNext ? "" : "disabled"}>Siguiente</button>
  </div>`;
}

export function showToast(message, kind = "success") {
  const region = document.querySelector("#toast-region");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${kind}`;
  toast.setAttribute("role", kind === "error" ? "alert" : "status");
  toast.textContent = message;
  region.append(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

export function openModal({ title, content, onClose } = {}) {
  const dialog = document.createElement("dialog");
  dialog.className = "app-modal";
  const heading = document.createElement("div");
  heading.className = "modal-header";
  const headingTitle = document.createElement("h2");
  headingTitle.textContent = title || "Información";
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "button button-quiet";
  closeButton.dataset.modalClose = "";
  closeButton.setAttribute("aria-label", "Cerrar");
  closeButton.textContent = "Cerrar";
  heading.append(headingTitle, closeButton);
  const modalContent = document.createElement("div");
  modalContent.className = "modal-content";
  dialog.append(heading, modalContent);
  modalContent.append(
    content instanceof Node ? content : document.createTextNode(String(content || ""))
  );
  const close = () => {
    dialog.close();
    dialog.remove();
    onClose?.();
  };
  closeButton.addEventListener("click", close);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) close();
  });
  dialog.addEventListener("close", () => dialog.remove(), { once: true });
  document.body.append(dialog);
  dialog.showModal();
  return { dialog, close };
}

export function initializeFormValidation(root = document) {
  root.addEventListener("invalid", (event) => {
    event.target.classList.add("is-invalid");
  }, true);
  root.addEventListener("input", (event) => {
    if (event.target instanceof HTMLInputElement
      && event.target.matches("[data-table-search]")) {
      const table = event.target.closest(".table-search").nextElementSibling;
      const term = event.target.value.trim().toLocaleLowerCase();
      table.querySelectorAll("[data-table-row]").forEach((row) => {
        const rowSearchText = (row.dataset.tableSearchText || row.textContent || "").toLocaleLowerCase();
        row.hidden = !rowSearchText.includes(term);
      });
      return;
    }
    if (event.target instanceof HTMLInputElement
      || event.target instanceof HTMLSelectElement
      || event.target instanceof HTMLTextAreaElement) {
      event.target.classList.toggle("is-invalid", !event.target.checkValidity());
    }
  });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}
