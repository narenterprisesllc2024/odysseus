// Tracker UI — reads/writes the 4-tier execution tracker via /api/tracker/*
(function () {
  "use strict";

  const sectionsEl = document.getElementById("sections");
  const todayLabel = document.getElementById("today-label");
  const refreshBtn = document.getElementById("refresh-btn");
  const toastEl = document.getElementById("toast");

  let toastTimer = null;
  function toast(msg, isError) {
    toastEl.textContent = msg;
    toastEl.classList.toggle("error", !!isError);
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2200);
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  function renderItems(section) {
    if (!section.items.length) {
      return `<div class="empty">(no items — add one below or via the markdown file)</div>`;
    }
    const firstUnchecked = section.items.find((i) => !i.checked);
    const nextUpHtml =
      section.id !== "daily_rhythm" && section.id !== "north_star" && firstUnchecked
        ? `<div class="next-up"><strong>Next up:</strong> ${escapeHtml(firstUnchecked.label)}</div>`
        : "";
    const itemsHtml = section.items
      .map(
        (item, idx) => `
        <li class="item ${item.checked ? "checked" : ""}" data-item-idx="${idx}">
          <input type="checkbox" ${item.checked ? "checked" : ""}
                 data-section-id="${section.id}"
                 data-item-label="${escapeHtml(item.label)}">
          <label>${escapeHtml(item.label)}</label>
        </li>`
      )
      .join("");
    return `${nextUpHtml}<ul class="items">${itemsHtml}</ul>`;
  }

  function renderProgress(section) {
    if (!section.items.length) return "";
    const checked = section.items.filter((i) => i.checked).length;
    const total = section.items.length;
    const pct = Math.round((checked / total) * 100);
    return `
      <div class="section-count">${checked}/${total}</div>
      <div class="progress-bar" style="grid-column: 1 / -1; width: 100%;">
        <div class="progress-fill" style="width:${pct}%"></div>
      </div>`;
  }

  function renderAddRow(section) {
    if (section.id === "north_star") return ""; // north star is curated
    return `
      <div class="add-row">
        <input type="text" placeholder="add to ${section.title.toLowerCase()}…"
               data-add-section="${section.id}"
               maxlength="240">
        <button data-add-btn="${section.id}">+ add</button>
      </div>`;
  }

  function render(state) {
    todayLabel.textContent = `Today · ${state.today}`;
    sectionsEl.innerHTML = state.sections
      .map((section) => {
        const checked = section.items.filter((i) => i.checked).length;
        const total = section.items.length;
        return `
        <div class="section" data-section-id="${section.id}">
          <div class="section-head">
            <div class="section-name">${section.emoji} ${section.title}
              <span class="section-sub">${section.subtitle}</span>
            </div>
            <div class="section-count">${checked}/${total}</div>
          </div>
          ${total ? `<div class="progress-bar"><div class="progress-fill" style="width:${total ? Math.round((checked/total)*100) : 0}%"></div></div>` : ""}
          ${renderItems(section)}
          ${renderAddRow(section)}
        </div>`;
      })
      .join("");
    wireCheckboxes();
    wireAddRows();
  }

  function wireCheckboxes() {
    sectionsEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.addEventListener("change", async () => {
        const sectionId = cb.dataset.sectionId;
        const itemLabel = cb.dataset.itemLabel;
        const want = cb.checked;
        try {
          const res = await fetch("/api/tracker/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              section_id: sectionId,
              item_label: itemLabel,
              checked: want,
            }),
            credentials: "same-origin",
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const li = cb.closest("li.item");
          if (li) li.classList.toggle("checked", want);
          toast(want ? "checked" : "unchecked");
          // Auto-reload to refresh "next up" + counts
          setTimeout(load, 250);
        } catch (e) {
          cb.checked = !want;
          toast("save failed: " + e.message, true);
        }
      });
    });
  }

  function wireAddRows() {
    sectionsEl.querySelectorAll("[data-add-btn]").forEach((btn) => {
      const sectionId = btn.dataset.addBtn;
      const input = sectionsEl.querySelector(`[data-add-section="${sectionId}"]`);
      const submit = async () => {
        const label = input.value.trim();
        if (!label) return;
        try {
          const res = await fetch("/api/tracker/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              section_id: sectionId,
              item_label: label,
              checked: false,
            }),
            credentials: "same-origin",
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          input.value = "";
          toast("added");
          load();
        } catch (e) {
          toast("add failed: " + e.message, true);
        }
      };
      btn.addEventListener("click", submit);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") submit();
      });
    });
  }

  async function load() {
    try {
      const res = await fetch("/api/tracker/state", { credentials: "same-origin" });
      if (res.status === 403) {
        sectionsEl.innerHTML = `<div class="empty">Not logged in. <a href="/login">Sign in</a> to view the tracker.</div>`;
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const state = await res.json();
      render(state);
    } catch (e) {
      sectionsEl.innerHTML = `<div class="empty">Failed to load: ${escapeHtml(e.message)}</div>`;
    }
  }

  refreshBtn.addEventListener("click", (e) => {
    e.preventDefault();
    load();
  });

  load();
  // Auto-refresh every 60s so multi-device edits surface
  setInterval(load, 60000);
})();
