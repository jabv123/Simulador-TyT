import { api } from "./api.js";
import { showToast } from "./components.js";

document.querySelectorAll("[data-report-export]").forEach((link) => {
  link.addEventListener("click", async (event) => {
    event.preventDefault();
    try {
      const workbook = await api(link.href);
      const objectUrl = URL.createObjectURL(workbook);
      const downloadLink = document.createElement("a");
      const report = link.dataset.reportExport.toLowerCase();
      const timestamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
      downloadLink.href = objectUrl;
      downloadLink.download = `reporte_academico_${report}_${timestamp}.xlsx`;
      downloadLink.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (error) {
      showToast(error.message, "error");
    }
  });
});

const form = document.querySelector("#report-filter-form");

if (form) {
  const anioSelect = form.elements.anio;
  const periodoSelect = form.elements.periodo;
  const cursoSelect = form.elements.curso;
  const cursoAcademicoSelect = form.elements.curso_academico;
  const grupoSelect = form.elements.grupo;
  const ejeSelect = form.elements.eje;
  const estudianteSelect = form.elements.estudiante;
  const activeFilters = document.querySelector("#active-filters");
  const apiBase = "/reportes/api";

  function renderActiveFilters() {
    const labels = [
      ["anio", "Año"],
      ["periodo", "Período"],
      ["curso_academico", "Curso académico"],
      ["grupo", "Grupo"],
      ["curso", "Simulacro"],
      ["eje", "Eje"],
      ["tipo", "Resumen"],
      ["query", "Búsqueda"],
      ["estudiante", "Estudiante"],
    ];
    const chips = [];

    labels.forEach(([key, label]) => {
      const field = form.elements[key];
      const value = field?.value || "";
      if (!value) return;
      const selectedText = field && field.tagName === "SELECT"
        ? field.selectedOptions[0]?.textContent?.trim() || ""
        : "";
      const text = selectedText || value;
      const pretty = text.length > 22 ? `${text.slice(0, 22)}…` : text;
      chips.push(`<span class="filter-chip"><strong>${label}:</strong> ${pretty}</span>`);
    });

    if (!chips.length) {
      chips.push('<span class="filter-chip is-empty">Todos los registros</span>');
    }
    activeFilters.innerHTML = chips.join("");
  }

  const option = (value, label) => {
    const element = document.createElement("option");
    element.value = value;
    element.textContent = label;
    return element;
  };

  function resetSelect(select, label = "Todos") {
    select.replaceChildren(option("", label));
  }

  function updateChildOptions(select, items, label = "Todos") {
    resetSelect(select, label);
    items.forEach((item) => {
      const value = item.value ?? item.id ?? item.pk ?? "";
      const text = item.label ?? item.nombre ?? item.codigo ?? item.name ?? value;
      if (value !== "") select.append(option(String(value), String(text)));
    });
  }

  function setSelectValue(select, value) {
    select.value = Array.from(select.options).some(
      (item) => String(item.value) === String(value),
    ) ? String(value) : "";
  }

  async function fetchJson(url) {
    return api(url, { headers: { Accept: "application/json" } });
  }

  async function refreshPeriodos() {
    const selectedPeriodo = periodoSelect.value;
    const params = new URLSearchParams();
    if (anioSelect.value) params.set("anio", anioSelect.value);
    const data = await fetchJson(`${apiBase}/periodos/?${params.toString()}`);
    updateChildOptions(periodoSelect, data);
    setSelectValue(periodoSelect, selectedPeriodo);
  }

  async function refreshCursos() {
    const selectedCurso = cursoSelect.value;
    const params = new URLSearchParams();
    if (anioSelect.value) params.set("anio", anioSelect.value);
    if (periodoSelect.value) params.set("periodo", periodoSelect.value);
    const data = await fetchJson(`${apiBase}/cursos/?${params.toString()}`);
    updateChildOptions(cursoSelect, data);
    setSelectValue(cursoSelect, selectedCurso);
  }

  async function refreshCursosAcademicos() {
    const selectedCurso = cursoAcademicoSelect.value;
    const data = await fetchJson(`${apiBase}/cursos-academicos/`);
    updateChildOptions(cursoAcademicoSelect, data);
    setSelectValue(cursoAcademicoSelect, selectedCurso);
  }

  async function refreshGrupos() {
    const selectedGrupo = grupoSelect.value;
    const params = new URLSearchParams();
    if (cursoAcademicoSelect.value) {
      params.set("curso_academico", cursoAcademicoSelect.value);
    }
    const data = await fetchJson(`${apiBase}/grupos/?${params.toString()}`);
    updateChildOptions(
      grupoSelect,
      data.map((item) => ({
        id: item.id,
        nombre: `${item.curso_nombre} · ${item.nombre}`,
      })),
    );
    setSelectValue(grupoSelect, selectedGrupo);
  }

  async function refreshEjes() {
    const selectedEje = ejeSelect.value;
    const params = new URLSearchParams();
    if (anioSelect.value) params.set("anio", anioSelect.value);
    if (periodoSelect.value) params.set("periodo", periodoSelect.value);
    if (cursoSelect.value) params.set("curso", cursoSelect.value);
    const data = await fetchJson(`${apiBase}/ejes/?${params.toString()}`);
    updateChildOptions(ejeSelect, data);
    setSelectValue(ejeSelect, selectedEje);
  }

  async function refreshEstudiantes() {
    const selectedEstudiante = estudianteSelect.value;
    const params = new URLSearchParams();
    if (cursoSelect.value) params.set("curso", cursoSelect.value);
    if (cursoAcademicoSelect.value) {
      params.set("curso_academico", cursoAcademicoSelect.value);
    }
    if (grupoSelect.value) params.set("grupo", grupoSelect.value);
    if (anioSelect.value) params.set("anio", anioSelect.value);
    if (periodoSelect.value) params.set("periodo", periodoSelect.value);
    const data = await fetchJson(`${apiBase}/estudiantes/?${params.toString()}`);
    updateChildOptions(
      estudianteSelect,
      data.map((item) => ({
        id: item.id,
        nombre: item.codigo ? `${item.nombre} (${item.codigo})` : item.nombre,
      })),
    );
    setSelectValue(estudianteSelect, selectedEstudiante);
  }

  async function refreshFiltersCascade() {
    try {
      await refreshPeriodos();
      await refreshCursos();
      await refreshCursosAcademicos();
      await refreshGrupos();
      await refreshEjes();
      await refreshEstudiantes();
      renderActiveFilters();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  anioSelect.addEventListener("change", async () => {
    periodoSelect.value = "";
    cursoSelect.value = "";
    cursoAcademicoSelect.value = "";
    grupoSelect.value = "";
    ejeSelect.value = "";
    estudianteSelect.value = "";
    await refreshFiltersCascade();
  });

  periodoSelect.addEventListener("change", async () => {
    cursoSelect.value = "";
    ejeSelect.value = "";
    estudianteSelect.value = "";
    await refreshFiltersCascade();
  });

  cursoSelect.addEventListener("change", async () => {
    ejeSelect.value = "";
    estudianteSelect.value = "";
    await refreshFiltersCascade();
  });

  cursoAcademicoSelect.addEventListener("change", async () => {
    grupoSelect.value = "";
    estudianteSelect.value = "";
    await refreshFiltersCascade();
  });

  grupoSelect.addEventListener("change", async () => {
    estudianteSelect.value = "";
    await refreshEstudiantes();
    renderActiveFilters();
  });

  estudianteSelect.addEventListener("change", renderActiveFilters);
  document.querySelector("#clear-filters").addEventListener("click", () => {
    form.reset();
    window.location.href = "/reportes/";
  });
  form.addEventListener("submit", renderActiveFilters);
  renderActiveFilters();
  refreshFiltersCascade();
}