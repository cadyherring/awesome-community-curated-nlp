const state = {
  records: [],
  selected: -1,
  currentDetail: null,
};

const el = (id) => document.getElementById(id);

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function buildQuery() {
  const params = new URLSearchParams();
  const q = el("search").value.trim();
  const status = el("filter-status").value;
  if (q) params.set("q", q);
  if (status) params.set("review_status", status);
  return params.toString();
}

async function loadList() {
  const qs = buildQuery();
  state.records = await api(`/api/records${qs ? "?" + qs : ""}`);
  renderList();
  if (state.records.length && state.selected === -1) {
    selectIndex(0);
  }
}

function renderList() {
  const list = el("record-list");
  list.innerHTML = "";
  state.records.forEach((r, i) => {
    const li = document.createElement("li");
    li.className = i === state.selected ? "selected" : "";
    li.innerHTML = `
      <div class="title">${escapeHtml(r.title || "(untitled " + r.record_type + ")")}</div>
      <div class="sub">#${r.id} &middot; ${r.record_date || "no date"}${r.record_date && !r.record_date_verified ? " (unverified)" : ""} &middot; ${r.review_status}</div>
    `;
    li.addEventListener("click", () => selectIndex(i));
    list.appendChild(li);
  });
}

function selectIndex(i) {
  if (i < 0 || i >= state.records.length) return;
  state.selected = i;
  renderList();
  loadDetail(state.records[i].id);
  const li = document.querySelectorAll("#record-list li")[i];
  if (li) li.scrollIntoView({ block: "nearest" });
}

async function loadDetail(id) {
  const data = await api(`/api/records/${id}`);
  state.currentDetail = data;
  renderDetail(data);
}

function statusSpan(verified, hasValue) {
  if (!hasValue) return "";
  return verified
    ? '<span class="status verified">verified</span>'
    : '<span class="status unverified">unverified (AI proposed)</span>';
}

function renderDetail(data) {
  el("detail-empty").hidden = true;
  el("detail-content").hidden = false;

  const r = data.record;
  el("d-title").textContent = r.title || `(untitled ${r.record_type})`;
  el("d-type").textContent = r.record_type;
  el("d-review-status").textContent = r.review_status;
  el("d-review-status").className = "badge " + r.review_status;

  el("d-date-input").value = r.record_date || "";
  el("d-date-status").innerHTML = statusSpan(r.record_date_verified, r.record_date);

  el("d-sig-input").value = r.significance || "";
  el("d-sig-status").innerHTML = statusSpan(r.significance_verified, r.significance);

  el("d-body").textContent = r.body_text;

  el("d-source").textContent = data.source
    ? `${data.source.original_name} — sha256:${data.source.sha256.slice(0, 16)}…`
    : "(no source)";

  const entitiesEl = el("d-entities");
  entitiesEl.innerHTML = "";
  data.entities.forEach((e) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span>${escapeHtml(e.name)}</span>
      ${statusSpan(e.verified, true)}
      ${!e.verified ? `<button class="tiny" data-verify-entity="${e.id}">verify</button>` : ""}
      <button class="tiny" data-reject-entity="${e.id}">remove</button>
    `;
    entitiesEl.appendChild(li);
  });

  const tagsEl = el("d-tags");
  tagsEl.innerHTML = "";
  data.tags.forEach((t) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span>${escapeHtml(t.name)}</span>
      ${statusSpan(t.verified, true)}
      ${!t.verified ? `<button class="tiny" data-verify-tag="${t.id}">verify</button>` : ""}
      <button class="tiny" data-reject-tag="${t.id}">remove</button>
    `;
    tagsEl.appendChild(li);
  });

  const linksEl = el("d-links");
  linksEl.innerHTML = "";
  data.links.forEach((l) => {
    const other = l.record_id_a === r.id ? l.record_id_b : l.record_id_a;
    const li = document.createElement("li");
    li.textContent = `#${other} (${l.relation_type})`;
    linksEl.appendChild(li);
  });

  wireDetailActions(r.id);
}

function wireDetailActions(recordId) {
  el("d-approve").onclick = async () => {
    await api(`/api/records/${recordId}/approve`, { method: "POST" });
    await refreshCurrent();
  };

  el("d-date-save").onclick = async () => {
    await api(`/api/records/${recordId}/date`, {
      method: "POST",
      body: JSON.stringify({ value: el("d-date-input").value || null }),
    });
    await refreshCurrent();
  };

  el("d-sig-save").onclick = async () => {
    await api(`/api/records/${recordId}/significance`, {
      method: "POST",
      body: JSON.stringify({ value: el("d-sig-input").value || null }),
    });
    await refreshCurrent();
  };

  document.querySelectorAll("[data-verify-entity]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/records/${recordId}/entities/${btn.dataset.verifyEntity}/verify`, { method: "POST" });
      await refreshCurrent();
    };
  });
  document.querySelectorAll("[data-reject-entity]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/records/${recordId}/entities/${btn.dataset.rejectEntity}/reject`, { method: "POST" });
      await refreshCurrent();
    };
  });
  document.querySelectorAll("[data-verify-tag]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/records/${recordId}/tags/${btn.dataset.verifyTag}/verify`, { method: "POST" });
      await refreshCurrent();
    };
  });
  document.querySelectorAll("[data-reject-tag]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/records/${recordId}/tags/${btn.dataset.rejectTag}/reject`, { method: "POST" });
      await refreshCurrent();
    };
  });

  el("d-tag-input").onkeydown = async (ev) => {
    if (ev.key === "Enter" && ev.target.value.trim()) {
      await api(`/api/records/${recordId}/tags`, {
        method: "POST",
        body: JSON.stringify({ name: ev.target.value.trim() }),
      });
      ev.target.value = "";
      await refreshCurrent();
    }
  };

  el("d-link-input").onkeydown = async (ev) => {
    if (ev.key === "Enter" && ev.target.value.trim()) {
      await api(`/api/records/${recordId}/links`, {
        method: "POST",
        body: JSON.stringify({ other_record_id: parseInt(ev.target.value, 10) }),
      });
      ev.target.value = "";
      await refreshCurrent();
    }
  };
}

async function refreshCurrent() {
  await loadList();
  if (state.selected >= 0 && state.records[state.selected]) {
    await loadDetail(state.records[state.selected].id);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

document.addEventListener("keydown", (ev) => {
  const tag = document.activeElement.tagName;
  const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

  if (ev.key === "/" && !typing) {
    ev.preventDefault();
    el("search").focus();
    return;
  }
  if (ev.key === "Escape" && typing) {
    document.activeElement.blur();
    return;
  }
  if (typing) return;

  if (ev.key === "j" || ev.key === "ArrowDown") {
    ev.preventDefault();
    selectIndex(state.selected + 1);
  } else if (ev.key === "k" || ev.key === "ArrowUp") {
    ev.preventDefault();
    selectIndex(state.selected - 1);
  } else if (ev.key === "a" && state.currentDetail) {
    ev.preventDefault();
    el("d-approve").click();
  }
});

el("search").addEventListener("input", debounce(() => { state.selected = -1; loadList(); }, 250));
el("filter-status").addEventListener("change", () => { state.selected = -1; loadList(); });

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

loadList();
