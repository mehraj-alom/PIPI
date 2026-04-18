function byId(id) {
  return document.getElementById(id);
}

function setStatus(el, message, ok) {
  el.textContent = message;
  el.classList.remove("ok", "err");
  if (!message) return;
  el.classList.add(ok ? "ok" : "err");
}

function pretty(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
}

function buildHeaders(sessionId) {
  const headers = {};
  if (sessionId && sessionId.trim()) {
    headers["x-session-id"] = sessionId.trim();
  }
  return headers;
}

function getContext() {
  return {
    apiBase: byId("apiBase").value.trim().replace(/\/+$/, ""),
    patientId: byId("patientId").value.trim(),
    sessionId: byId("sessionId").value.trim(),
  };
}

async function submitSkin(event) {
  event.preventDefault();

  const statusEl = byId("skinStatus");
  const outputEl = byId("skinOutput");
  const submitBtn = event.currentTarget.querySelector("button[type='submit']");

  const file = byId("skinFile").files[0];
  const { apiBase, patientId, sessionId } = getContext();

  if (!file) {
    setStatus(statusEl, "Select an image first.", false);
    return;
  }

  if (!apiBase) {
    setStatus(statusEl, "Enter API base URL.", false);
    return;
  }

  const form = new FormData();
  form.append("file", file);
  if (patientId) form.append("patient_id", patientId);

  try {
    submitBtn.disabled = true;
    setStatus(statusEl, "Uploading skin image...", true);
    outputEl.textContent = "";

    const res = await fetch(`${apiBase}/Skin/SKIN_TELLIGENT`, {
      method: "POST",
      headers: buildHeaders(sessionId),
      body: form,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || data.detail || `Request failed (${res.status})`);
    }

    setStatus(statusEl, "Skin upload completed.", true);
    outputEl.textContent = pretty(data);
  } catch (error) {
    setStatus(statusEl, error.message || "Upload failed.", false);
    outputEl.textContent = "";
  } finally {
    submitBtn.disabled = false;
  }
}

async function submitDoc(event) {
  event.preventDefault();

  const statusEl = byId("docStatus");
  const outputEl = byId("docOutput");
  const submitBtn = event.currentTarget.querySelector("button[type='submit']");

  const file = byId("docFile").files[0];
  const reportType = byId("reportType").value;
  const { apiBase, patientId, sessionId } = getContext();

  if (!file) {
    setStatus(statusEl, "Select a document first.", false);
    return;
  }

  if (!apiBase) {
    setStatus(statusEl, "Enter API base URL.", false);
    return;
  }

  const form = new FormData();
  form.append("file", file);
  form.append("report_type", reportType);
  if (patientId) form.append("patient_id", patientId);

  try {
    submitBtn.disabled = true;
    setStatus(statusEl, "Uploading document...", true);
    outputEl.textContent = "";

    const res = await fetch(`${apiBase}/ade/upload`, {
      method: "POST",
      headers: buildHeaders(sessionId),
      body: form,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || data.detail || `Request failed (${res.status})`);
    }

    setStatus(statusEl, "Document upload completed.", true);
    outputEl.textContent = pretty(data);
  } catch (error) {
    setStatus(statusEl, error.message || "Upload failed.", false);
    outputEl.textContent = "";
  } finally {
    submitBtn.disabled = false;
  }
}

function init() {
  byId("skinForm").addEventListener("submit", submitSkin);
  byId("docForm").addEventListener("submit", submitDoc);
}

init();
