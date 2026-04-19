function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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

function getToastRoot() {
  let root = byId("toast-root");
  if (!root) {
    root = document.createElement("div");
    root.id = "toast-root";
    root.className = "toast-root";
    root.setAttribute("aria-live", "polite");
    root.setAttribute("aria-atomic", "true");
    document.body.appendChild(root);
  }
  return root;
}

function showToast(title, message, kind = "success") {
  const root = getToastRoot();
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("data-kind", kind);
  toast.innerHTML = `
    <p class="toast__title">${escapeHtml(title)}</p>
    <p class="toast__message">${escapeHtml(message)}</p>
  `;
  root.appendChild(toast);

  window.setTimeout(() => {
    toast.remove();
  }, 3600);

  return toast;
}

window.pipiNotify = showToast;

function buildHeaders(sessionId) {
  const headers = {};
  if (sessionId && sessionId.trim()) {
    headers["x-session-id"] = sessionId.trim();
  }
  return headers;
}

function resolveApiBase() {
  const explicit = document.body?.dataset?.apiBase || "";
  const cleaned = explicit.trim().replace(/\/+$/, "");
  if (cleaned) return cleaned;
  return "http://127.0.0.1:8000";
}

function getContext() {
  return {
    apiBase: resolveApiBase(),
    patientId: byId("patientId").value.trim(),
    sessionId: byId("sessionId").value.trim(),
  };
}

function toApiUrl(apiBase, filePath) {
  const rawPath = String(filePath || "").trim();
  if (!rawPath) return "";
  if (/^https?:\/\//i.test(rawPath)) return rawPath;
  const cleanPath = rawPath.replace(/^\.\//, "").replace(/^\/+/, "").replace(/\\/g, "/");
  return `${apiBase}/${cleanPath}`;
}

function buildResultCard(title, summary, caution) {
  const card = document.createElement("section");
  card.className = "result-card";

  const header = document.createElement("div");
  header.className = "result-card__header";
  header.innerHTML = `
    <p class="result-card__eyebrow">Submitted</p>
    <h3>${escapeHtml(title)}</h3>
    <p class="result-card__summary">${escapeHtml(summary)}</p>
    <p class="result-card__caution">${escapeHtml(caution)}</p>
  `;

  card.appendChild(header);
  return card;
}

function wireToggle(button, panel) {
  button.addEventListener("click", () => {
    const hidden = panel.classList.contains("hidden");
    panel.classList.toggle("hidden");
    button.textContent = hidden ? "Hide Result" : "See Result";
  });
}

function renderSkinResult(data, apiBase) {
  const outputEl = byId("skinOutput");
  outputEl.innerHTML = "";

  const result = Array.isArray(data.classification_results) ? data.classification_results[0] : null;
  const output = data.output || {};
  const confidence = Number(result?.confidence ?? 0);
  const caution = confidence >= 0.8
    ? "High-confidence inference. Treat this as educational output, not a diagnosis."
    : confidence >= 0.6
      ? "Uncertain inference. Please verify the result with a clinician."
      : "Low-confidence inference. Clinical review is recommended.";

  const card = buildResultCard(
    "Skin image processed",
    "The detected region is shown below. Tap See Result to open the predicted class and Grad-CAM explainability.",
    caution,
  );

  const detectionImageUrl = toApiUrl(apiBase, output.detection_boxes_image || output.boxed_image || output.original_image);
  if (detectionImageUrl) {
    const figure = document.createElement("figure");
    figure.className = "result-card__figure";
    figure.innerHTML = `<img src="${escapeHtml(detectionImageUrl)}" alt="Detected region with bounding boxes" />`;
    card.appendChild(figure);
  }

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "result-card__toggle";
  toggleBtn.textContent = "See Result";
  card.appendChild(toggleBtn);

  const details = document.createElement("div");
  details.className = "result-card__details hidden";

  const detailGrid = document.createElement("div");
  detailGrid.className = "result-card__detail-grid";

  const predictionBlock = document.createElement("div");
  predictionBlock.className = "result-card__detail-block";
  predictionBlock.innerHTML = `
    <h4>Classified result</h4>
    <p><strong>Top class:</strong> ${escapeHtml(result?.class_name || "Unavailable")}</p>
    <p><strong>Confidence:</strong> ${Number.isFinite(confidence) ? `${(confidence * 100).toFixed(1)}%` : "Unavailable"}</p>
  `;

  const gradcamBlock = document.createElement("div");
  gradcamBlock.className = "result-card__detail-block";
  const gradcamUrl = toApiUrl(apiBase, result?.gradcam || result?.top_3_gradcams?.[0]?.gradcam || "");
  gradcamBlock.innerHTML = `<h4>Grad-CAM</h4>`;
  if (gradcamUrl) {
    gradcamBlock.innerHTML += `<figure class="result-card__detail-image"><img src="${escapeHtml(gradcamUrl)}" alt="Grad-CAM explainability map" /></figure>`;
  } else {
    gradcamBlock.innerHTML += `<p>Grad-CAM preview is not available for this result.</p>`;
  }

  detailGrid.appendChild(predictionBlock);
  detailGrid.appendChild(gradcamBlock);
  details.appendChild(detailGrid);
  card.appendChild(details);

  wireToggle(toggleBtn, details);
  outputEl.appendChild(card);
}

function renderDocumentResult(data) {
  const outputEl = byId("docOutput");
  outputEl.innerHTML = "";

  const fields = data.medical_fields || {};
  const summary = fields.summary || `Document processed successfully using ${data.engine || "the selected engine"}.`;
  const caution = "Educational extraction only. Verify against the source report before use.";

  const card = buildResultCard(
    "Document processed",
    "The submission is complete. Tap See Result to open the parsed markdown and extracted fields.",
    caution,
  );

  const stats = document.createElement("div");
  stats.className = "result-card__detail-block";
  stats.innerHTML = `
    <h4>Submission summary</h4>
    <p><strong>Engine:</strong> ${escapeHtml(data.engine || "unknown")}</p>
    <p><strong>Chunks parsed:</strong> ${escapeHtml(data.chunk_count ?? 0)}</p>
    <p><strong>Summary:</strong> ${escapeHtml(summary)}</p>
  `;

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "result-card__toggle";
  toggleBtn.textContent = "See Result";

  const details = document.createElement("div");
  details.className = "result-card__details hidden";

  const detailGrid = document.createElement("div");
  detailGrid.className = "result-card__detail-grid";

  const markdownBlock = document.createElement("div");
  markdownBlock.className = "result-card__detail-block";
  markdownBlock.innerHTML = `
    <h4>Parsed markdown</h4>
    <pre class="result-card__markdown"></pre>
  `;
  markdownBlock.querySelector("pre").textContent = data.markdown || "";

  const fieldsBlock = document.createElement("div");
  fieldsBlock.className = "result-card__detail-block";
  fieldsBlock.innerHTML = `
    <h4>Extracted fields</h4>
    <pre class="result-card__json"></pre>
  `;
  fieldsBlock.querySelector("pre").textContent = pretty(fields);

  detailGrid.appendChild(markdownBlock);
  detailGrid.appendChild(fieldsBlock);
  details.appendChild(detailGrid);

  card.appendChild(stats);
  card.appendChild(toggleBtn);
  card.appendChild(details);

  wireToggle(toggleBtn, details);
  outputEl.appendChild(card);
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
    renderSkinResult(data, apiBase);
    showToast("Skin submitted", "Bounding boxes are visible now. Tap See Result for the class and Grad-CAM.", "success");
  } catch (error) {
    setStatus(statusEl, error.message || "Upload failed.", false);
    outputEl.textContent = "";
    showToast("Skin upload failed", error.message || "Upload failed.", "error");
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
    renderDocumentResult(data);
    showToast("Document submitted", "Tap See Result to review the parsed report details.", "success");
  } catch (error) {
    setStatus(statusEl, error.message || "Upload failed.", false);
    outputEl.textContent = "";
    showToast("Document upload failed", error.message || "Upload failed.", "error");
  } finally {
    submitBtn.disabled = false;
  }
}

function init() {
  byId("skinForm").addEventListener("submit", submitSkin);
  byId("docForm").addEventListener("submit", submitDoc);
}

init();
