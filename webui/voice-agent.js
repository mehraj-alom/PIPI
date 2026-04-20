/* ============================================================
   PIPI Voice Agent — Phone Call Controller
   ElevenLabs WebRTC session, 9 client tools, upload modal,
   canvas waveform, call state machine
   ============================================================ */

// ── ElevenLabs SDK (ESM via CDN) ────────────────────────────
// Loaded dynamically to avoid hard import failure if CDN is down
let Conversation = null;

async function loadSDK() {
  if (Conversation) return;
  try {
    const mod = await import('https://cdn.jsdelivr.net/npm/@elevenlabs/client@latest/+esm');
    Conversation = mod.Conversation;
    if (!Conversation) throw new Error('Conversation class not found in SDK');
  } catch (e) {
    console.error('[VoiceAgent] Failed to load ElevenLabs SDK:', e);
    throw new Error('Could not load voice SDK. Check your internet connection.');
  }
}

// ── Configuration ───────────────────────────────────────────
const DEFAULT_AGENT_ID = 'YOUR_AGENT_ID';
let AGENT_ID = DEFAULT_AGENT_ID;
let agentConfigPromise = null;
let lastAgentConfigError = null;
let signedUrlPromise = null;

async function ensureAgentId(forceRefresh = false) {
  if (!forceRefresh && AGENT_ID && AGENT_ID !== DEFAULT_AGENT_ID) return AGENT_ID;
  if (agentConfigPromise) return agentConfigPromise;

  const apiBase = getApiBase();
  agentConfigPromise = (async () => {
    try {
      const res = await fetch(`${apiBase}/tools/VoiceAgent/config`);
      if (!res.ok) throw new Error(`Config request failed (${res.status})`);

      const data = await res.json();
      const candidate = normalizeAgentId(String(data?.agent_id || '').trim());
      if (candidate) {
        AGENT_ID = candidate;
      }
      lastAgentConfigError = null;
      return AGENT_ID;
    } catch (err) {
      lastAgentConfigError = err;
      console.warn('[VoiceAgent] Failed to load AGENT_ID from backend config:', err);
      return AGENT_ID;
    } finally {
      agentConfigPromise = null;
    }
  })();

  return agentConfigPromise;
}

function normalizeAgentId(rawAgentId) {
  const raw = String(rawAgentId || '').trim();
  if (!raw) return '';

  const agentMatch = raw.match(/agent_[a-z0-9]+/i);
  if (!agentMatch) return raw;

  const branchMatch = raw.match(/agtbrch_[a-z0-9]+/i);
  if (!branchMatch) return agentMatch[0];

  return `${agentMatch[0]}?branchId=${branchMatch[0]}`;
}

function getAgentStartCandidates(agentId) {
  const normalized = normalizeAgentId(agentId);
  if (!normalized) return [];

  const candidates = [normalized];
  const baseId = normalized.split('?')[0];
  if (baseId && baseId !== normalized) {
    candidates.push(baseId);
  }
  return candidates;
}

function isTokenFetch400Error(error) {
  const text = String(error?.message || '').toLowerCase();
  return text.includes('failed to fetch conversation token')
    && text.includes('api returned 400');
}

async function fetchSignedUrl() {
  if (signedUrlPromise) return signedUrlPromise;

  const apiBase = getApiBase();
  signedUrlPromise = (async () => {
    const res = await fetch(`${apiBase}/tools/VoiceAgent/signed-url`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data?.detail || `Signed URL request failed (${res.status})`);
    }

    const signedUrl = String(data?.signed_url || '').trim();
    if (!signedUrl) {
      throw new Error('Signed URL missing from backend response.');
    }
    return signedUrl;
  })();

  try {
    return await signedUrlPromise;
  } finally {
    signedUrlPromise = null;
  }
}

function shouldTryWebSocketFallback(error) {
  const errorText = String(error?.message || '').toLowerCase();
  return errorText.includes('failed to fetch conversation token')
    || errorText.includes('could not establish pc connection')
    || errorText.includes('failed to establish pc connection')
    || errorText.includes('ice')
    || errorText.includes('webrtc')
    || errorText.includes('timed out');
}

function mapVoiceStartError(error) {
  const errorText = String(error?.message || '').toLowerCase();

  if (error?.name === 'NotAllowedError') {
    return 'Microphone access denied';
  }

  if (errorText.includes('failed to fetch conversation token')) {
    return 'Invalid or inactive ElevenLabs agent/branch configuration';
  }

  if (errorText.includes('could not establish pc connection') || errorText.includes('failed to establish pc connection')) {
    return 'WebRTC peer connection failed. Disable VPN/firewall blocks and try a different network.';
  }

  if (errorText.includes('ice') || errorText.includes('webrtc')) {
    return 'Network blocked WebRTC connectivity. Check firewall/VPN and retry.';
  }

  return error?.message || 'Connection failed';
}

function startSessionWithTimeout(startSessionPromise, timeoutMs = 20000) {
  return Promise.race([
    startSessionPromise,
    new Promise((_, reject) => {
      setTimeout(() => {
        reject(new Error('Call setup timed out. Check network/VPN and retry.'));
      }, timeoutMs);
    }),
  ]);
}

// ── State ───────────────────────────────────────────────────
let conversation = null;
let timerInterval = null;
let timerSeconds = 0;
let currentMode = 'idle'; // idle | connecting | ringing | active | ended | error
let waveformRAF = null;
let callAttemptSeq = 0;
let voiceUiInitialized = false;

// ── DOM refs (populated in init) ────────────────────────────
const $ = (id) => document.getElementById(id);

// ── Helpers ─────────────────────────────────────────────────
function getApiBase() {
  const el = $('apiBase');
  const inputValue = el ? el.value.trim().replace(/\/+$/, '') : '';
  if (inputValue) return inputValue;

  const bodyValue = (document.body?.dataset?.apiBase || '').trim().replace(/\/+$/, '');
  if (bodyValue) return bodyValue;

  const host = window.location?.hostname || '';
  const isLocalHost = ['localhost', '127.0.0.1', '0.0.0.0'].includes(host);
  if (window.location?.origin && !isLocalHost) {
    return window.location.origin;
  }

  return 'http://127.0.0.1:8000';
}

function timeStr() {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function notifyToast(title, message, kind = 'success') {
  if (typeof window.pipiNotify === 'function') {
    window.pipiNotify(title, message, kind);
  }
}

function titleCaseEndpoint(endpoint) {
  return String(endpoint)
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/([_-])/g, ' ')
    .trim();
}

function notifyToolOutcome(endpoint, data) {
  const errorMessage = data && typeof data === 'object' ? data.error : '';
  if (errorMessage) {
    notifyToast(titleCaseEndpoint(endpoint), errorMessage, 'error');
    return;
  }

  switch (endpoint) {
    case 'getPatientDetails':
      notifyToast('Patient found', data?.name ? `${data.name} is available in the record.` : 'Patient record loaded.', 'success');
      break;
    case 'registerNewPatient':
      notifyToast('Patient registered', data?.patient_id ? `Patient ID ${data.patient_id} saved successfully.` : 'Patient details saved successfully.', 'success');
      break;
    case 'searchDoctors':
      notifyToast('Doctors found', `${Array.isArray(data?.doctors) ? data.doctors.length : 0} doctor(s) matched your search.`, 'success');
      break;
    case 'checkDoctorAvailability':
      notifyToast('Availability checked', Array.isArray(data?.available_slots) && data.available_slots.length > 0 ? `${data.available_slots.length} slot(s) available.` : 'No slots matched the requested time.', Array.isArray(data?.available_slots) && data.available_slots.length > 0 ? 'success' : 'warning');
      break;
    case 'bookAppointment':
      notifyToast(
        data?.already_booked ? 'Appointment already booked' : 'Doctor booked',
        data?.appointment_id
          ? (data?.already_booked
            ? `Appointment ${data.appointment_id} was already confirmed.`
            : `Appointment ${data.appointment_id} has been scheduled.`)
          : 'Appointment scheduled successfully.',
        'success',
      );
      break;
    case 'cancelAppointment':
      notifyToast('Appointment cancelled', data?.appointment_id ? `Appointment ${data.appointment_id} was cancelled.` : 'Appointment cancelled successfully.', 'success');
      break;
    case 'getPatientAppointments':
      notifyToast('Appointments loaded', `${Array.isArray(data?.appointments) ? data.appointments.length : 0} appointment(s) retrieved.`, 'success');
      break;
    case 'rescheduleAppointment':
      notifyToast('Appointment rescheduled', data?.appointment_id ? `Appointment ${data.appointment_id} moved to ${data.new_date || 'the new date'}.` : 'Appointment rescheduled successfully.', 'success');
      break;
    default:
      notifyToast(titleCaseEndpoint(endpoint), 'Request completed successfully.', 'success');
      break;
  }
}

function syncCaseContextFromToolResult(endpoint, data) {
  if (!data || typeof data !== 'object') return;

  if ((endpoint === 'getPatientDetails' || endpoint === 'registerNewPatient') && data.patient_id) {
    const patientIdInput = $('patientId');
    if (patientIdInput) {
      patientIdInput.value = String(data.patient_id);
    }
  }
}

function syncVoiceBackdrop() {
  const widget = $('phone-widget');
  const body = document.body;
  if (!widget || !body) return;

  const isExpanded = widget.getAttribute('data-state') === 'expanded';
  const uploadModalVisible = $('upload-modal') && !$('upload-modal').classList.contains('hidden');
  body.classList.toggle('voice-agent-backdrop-active', isExpanded || uploadModalVisible);
}

function normalizeUploadType(uploadType) {
  const raw = String(uploadType || '').trim().toLowerCase();
  if (!raw) return 'lab_report';

  if (raw === 'skin_image' || raw.includes('skin')) return 'skin_image';
  if (raw === 'prescription' || raw.includes('prescription')) return 'prescription';
  if (
    raw === 'lab_report'
    || raw.includes('lab')
    || raw.includes('report')
    || raw.includes('document')
    || raw.includes('record')
    || raw.includes('medical')
  ) {
    return 'lab_report';
  }

  return 'lab_report';
}

function hasMicrophoneSupport() {
  return typeof navigator !== 'undefined'
    && typeof navigator.mediaDevices?.getUserMedia === 'function';
}

// ================================================================
//  1. SESSION LIFECYCLE
// ================================================================

async function startCall() {
  if (conversation) return;
  const attemptId = ++callAttemptSeq;

  await ensureAgentId();
  if (AGENT_ID === DEFAULT_AGENT_ID) {
    await ensureAgentId(true);
  }

  if (AGENT_ID === DEFAULT_AGENT_ID) {
    const configLoadFailed = !!lastAgentConfigError;
    const errorMessage = configLoadFailed
      ? `Could not load voice config from backend (${getApiBase()}). Check API Base URL and backend status.`
      : 'Set ELEVENLABS_AGENT_ID in .env and restart backend';
    setCallState('error', errorMessage);
    return;
  }

  try {
    setCallState('connecting');

    if (!hasMicrophoneSupport()) {
      throw new Error('Microphone access is unavailable in this browser context. Use HTTPS or localhost in a supported browser.');
    }

    // Load SDK if not loaded
    await loadSDK();

    // Request microphone
    const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    micStream.getTracks().forEach((track) => track.stop());
    setCallState('ringing');

    const sessionHandlers = {
      clientTools: buildClientTools(),
      onConnect: () => {
        if (attemptId !== callAttemptSeq) return;
        // Force output volume on connect in case stale mute state persists.
        if (conversation?.setVolume) {
          conversation.setVolume({ volume: 1 });
        }
        setCallState('active');
        startTimer();
      },
      onDisconnect: () => {
        if (attemptId !== callAttemptSeq) return;
        setCallState('ended');
        stopTimer();
        conversation = null;
      },
      onModeChange: ({ mode }) => {
        if (attemptId !== callAttemptSeq) return;
        updateAgentMode(mode);
      },
      onError: (e) => {
        if (attemptId !== callAttemptSeq) return;
        console.error('[VoiceAgent] Session error:', e);
        setCallState('error', mapVoiceStartError(e));
        stopTimer();
        conversation = null;
      },
    };

    let lastError = null;
    let attemptedWebSocketFallback = false;
    let usedWebSocketFallback = false;
    const candidateAgentIds = getAgentStartCandidates(AGENT_ID);
    for (let i = 0; i < candidateAgentIds.length; i += 1) {
      const candidateAgentId = candidateAgentIds[i];
      try {
        const startedSession = await startSessionWithTimeout(
          Conversation.startSession({
            agentId: candidateAgentId,
            ...sessionHandlers,
          }),
          20000,
        );

        if (attemptId !== callAttemptSeq) {
          try {
            await startedSession.endSession();
          } catch {
            // ignore late cleanup errors
          }
          throw new Error('Call was superseded by a newer attempt.');
        }

        conversation = startedSession;

        AGENT_ID = candidateAgentId;
        lastError = null;
        break;
      } catch (sessionErr) {
        lastError = sessionErr;
        const canRetryWithoutBranch = i < candidateAgentIds.length - 1
          && candidateAgentId.includes('?branchId=')
          && isTokenFetch400Error(sessionErr);
        if (canRetryWithoutBranch) {
          console.warn('[VoiceAgent] Token fetch failed for branch; retrying with base agent ID.');
          continue;
        }
        break;
      }
    }

    if (!conversation && lastError && shouldTryWebSocketFallback(lastError)) {
      attemptedWebSocketFallback = true;
      console.warn('[VoiceAgent] Retrying with WebSocket transport after WebRTC setup failure.');

      for (let i = 0; i < candidateAgentIds.length; i += 1) {
        const candidateAgentId = candidateAgentIds[i];
        try {
          const startedSession = await startSessionWithTimeout(
            Conversation.startSession({
              agentId: candidateAgentId,
              connectionType: 'websocket',
              ...sessionHandlers,
            }),
            20000,
          );

          if (attemptId !== callAttemptSeq) {
            try {
              await startedSession.endSession();
            } catch {
              // ignore late cleanup errors
            }
            throw new Error('Call was superseded by a newer attempt.');
          }

          conversation = startedSession;
          AGENT_ID = candidateAgentId;
          usedWebSocketFallback = true;
          lastError = null;
          break;
        } catch (sessionErr) {
          lastError = sessionErr;
        }
      }
    }

    if (!conversation && attemptedWebSocketFallback) {
      try {
        const signedUrl = await fetchSignedUrl();
        const startedSession = await startSessionWithTimeout(
          Conversation.startSession({
            signedUrl,
            connectionType: 'websocket',
            ...sessionHandlers,
          }),
          20000,
        );

        if (attemptId !== callAttemptSeq) {
          try {
            await startedSession.endSession();
          } catch {
            // ignore late cleanup errors
          }
          throw new Error('Call was superseded by a newer attempt.');
        }

        conversation = startedSession;
        usedWebSocketFallback = true;
        lastError = null;
      } catch (signedUrlErr) {
        lastError = signedUrlErr;
      }
    }

    if (usedWebSocketFallback) {
      notifyToast('Voice connection fallback', 'Connected over WebSocket because WebRTC was unavailable.', 'warning');
    }

    if (lastError && !conversation) {
      throw lastError;
    }
  } catch (err) {
    console.error('[VoiceAgent] Failed to start call:', err);
    const msg = mapVoiceStartError(err);
    setCallState('error', msg);
    conversation = null;
  }
}

async function endCall() {
  callAttemptSeq += 1;
  if (conversation) {
    try {
      await conversation.endSession();
    } catch { /* ignore */ }
    conversation = null;
  }
  stopTimer();
  setCallState('idle');
}

// ================================================================
//  2. THE 9 CLIENT TOOLS
// ================================================================

function buildClientTools() {
  const API = getApiBase();

  // Generic REST tool for endpoints 1-8
  const restTool = (endpoint, icon) => async (params) => {
    logTool(icon, endpoint, params, 'pending');
    try {
      const res = await fetch(`${API}/tools/VoiceAgent/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      const data = await res.json();
      logTool(icon, endpoint, data, 'done');
      syncCaseContextFromToolResult(endpoint, data);
      notifyToolOutcome(endpoint, data);
      return JSON.stringify(data);
    } catch (err) {
      const errObj = { error: err.message };
      logTool(icon, endpoint, errObj, 'error');
      notifyToast(titleCaseEndpoint(endpoint), err.message || 'Request failed', 'error');
      return JSON.stringify(errObj);
    }
  };

  return {
    getPatientDetails:       restTool('getPatientDetails', '🔍'),
    registerNewPatient:      restTool('registerNewPatient', '📋'),
    searchDoctors:           restTool('searchDoctors', '🩺'),
    checkDoctorAvailability: restTool('checkDoctorAvailability', '📅'),
    bookAppointment:         restTool('bookAppointment', '✅'),
    cancelAppointment:       restTool('cancelAppointment', '❌'),
    getPatientAppointments:  restTool('getPatientAppointments', '📃'),
    rescheduleAppointment:   restTool('rescheduleAppointment', '🔄'),

    // Tool 9: In-UI Upload
    requestUpload: (params) => handleUploadRequest(params, 'requestUpload'),
    sendUploadLink: (params) => handleUploadRequest(params, 'sendUploadLink'),
  };
}

// ================================================================
//  3. UPLOAD MODAL HANDLER (Tool 9)
// ================================================================

function syncUploadPanels(uploadType, data, apiBase) {
  if (!data || typeof data !== 'object' || data.error) return;

  if (uploadType === 'skin_image') {
    if (typeof window.setStatus === 'function') {
      window.setStatus($('skinStatus'), 'Skin upload completed.', true);
    }
    if (typeof window.renderSkinResult === 'function') {
      window.renderSkinResult(data, apiBase);
    }
    notifyToast('Skin submitted', 'The skin photo was uploaded in this web session.', 'success');
    return;
  }

  if (typeof window.setStatus === 'function') {
    window.setStatus($('docStatus'), 'Document upload completed.', true);
  }
  if (typeof window.renderDocumentResult === 'function') {
    window.renderDocumentResult(data);
  }
  notifyToast('Document submitted', 'The document was uploaded in this web session.', 'success');
}

function syncUploadFailure(uploadType, message) {
  if (uploadType === 'skin_image') {
    if (typeof window.setStatus === 'function') {
      window.setStatus($('skinStatus'), message, false);
    }
    return;
  }

  if (typeof window.setStatus === 'function') {
    window.setStatus($('docStatus'), message, false);
  }
}

async function handleUploadRequest(params, toolName = 'requestUpload') {
  const upload_type = normalizeUploadType(params?.upload_type); // "skin_image" | "lab_report" | "prescription"
  const API = getApiBase();
  const patientId = $('patientId')?.value?.trim() || '';
  const sessionId = $('sessionId')?.value?.trim() || '';

  const isSkin = upload_type === 'skin_image';
  const displayName = isSkin ? 'Skin Image' : upload_type.replace(/_/g, ' ');

  logTool('📸', toolName, { upload_type }, 'pending');

  const result = await new Promise((resolve) => {
    const modal = $('upload-modal');
    if (!modal) {
      resolve(JSON.stringify({ error: 'Upload modal is unavailable in this page.' }));
      return;
    }

    // ── Build modal HTML ──
    modal.innerHTML = `
      <div class="upload-modal-card">
        <div class="upload-modal-header">
          <span class="upload-icon">${isSkin ? '🔬' : '📄'}</span>
          <h4>Upload ${displayName}</h4>
          <p class="upload-hint">${isSkin
            ? 'Take a photo or select an image of the affected skin area'
            : 'Select your medical document (PDF, PNG, JPG)'
          }</p>
        </div>

        <label class="upload-dropzone" id="upload-dropzone">
          <input type="file" id="upload-file"
            accept="${isSkin ? 'image/*' : '.pdf,.png,.jpg,.jpeg'}"
            ${isSkin ? 'capture="environment"' : ''} />
          <span class="dropzone-text">
            <span class="dropzone-icon">${isSkin ? '📷' : '📁'}</span>
            <span>${isSkin ? 'Tap to take photo or select' : 'Tap to select file'}</span>
          </span>
        </label>

        <div id="upload-preview" class="upload-preview hidden"></div>

        <div id="upload-progress" class="upload-progress hidden">
          <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
          </div>
          <p class="progress-text" id="progress-text">Uploading...</p>
        </div>

        <button id="upload-cancel" class="upload-cancel-btn">Cancel</button>
      </div>
    `;

    modal.classList.remove('hidden');
    syncVoiceBackdrop();

    // ── Wire events ──
    const fileInput = $('upload-file');
    const cancelBtn = $('upload-cancel');

    cancelBtn.onclick = () => {
      modal.classList.add('hidden');
      syncVoiceBackdrop();
      resolve(JSON.stringify({ cancelled: true, message: 'User cancelled the upload.' }));
    };

    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      if (!file) return;

      const previewEl = $('upload-preview');
      const progressEl = $('upload-progress');
      const progressFill = $('progress-fill');
      const progressText = $('progress-text');

      // Show image preview
      if (file.type.startsWith('image/')) {
        const url = URL.createObjectURL(file);
        previewEl.innerHTML = `<img src="${url}" alt="Preview" />`;
        previewEl.classList.remove('hidden');
      } else {
        previewEl.innerHTML = `<p style="color: var(--va-text-muted); text-align:center; font-size:0.85rem; padding:12px;">📄 ${file.name}</p>`;
        previewEl.classList.remove('hidden');
      }

      // Show progress
      progressEl.classList.remove('hidden');
      progressFill.classList.add('indeterminate');
      progressText.textContent = `Analyzing ${displayName.toLowerCase()}...`;

      // Build request
      const headers = {};
      if (sessionId) headers['x-session-id'] = sessionId;

      const form = new FormData();
      form.append('file', file);
      if (patientId) form.append('patient_id', patientId);
      if (!isSkin && upload_type) form.append('report_type', upload_type);

      const endpoint = isSkin
        ? `${API}/Skin/SKIN_TELLIGENT`
        : `${API}/ade/upload`;

      try {
        const res = await fetch(endpoint, { method: 'POST', headers, body: form });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.error || data.detail || `Upload failed (${res.status})`);
        }

        syncUploadPanels(upload_type, data, API);

        // Success state
        progressFill.classList.remove('indeterminate');
        progressFill.style.width = '100%';
        progressText.textContent = '✓ Upload complete! Results updated on the page.';
        progressText.classList.add('success');

        // Auto-close
        setTimeout(() => {
          modal.classList.add('hidden');
          syncVoiceBackdrop();
        }, 1500);

        resolve(JSON.stringify(data));
      } catch (err) {
        syncUploadFailure(upload_type, err.message || 'Upload failed');
        progressFill.classList.remove('indeterminate');
        progressText.textContent = '✗ Upload failed — ' + (err.message || 'Unknown error');
        progressText.classList.add('error');

        setTimeout(() => {
          modal.classList.add('hidden');
          syncVoiceBackdrop();
        }, 2500);

        resolve(JSON.stringify({ error: err.message || 'Upload failed' }));
      }
    };
  });

  logTool('📸', toolName, JSON.parse(result), 'done');
  return result;
}

// ================================================================
//  4. CALL STATE MACHINE
// ================================================================

function setCallState(state, detail) {
  currentMode = state;
  const statusEl = $('call-status');
  const avatarEl = $('caller-avatar');
  const callBtn = $('btn-call');
  const endBtn = $('btn-end');
  const muteBtn = $('btn-mute');
  const timerEl = $('call-timer');
  const modeEl = $('mode-indicator');

  const config = {
    idle:       { text: 'Tap to call',    color: '#8892a4', avatarAnim: '',       showEnd: false, showCall: true,  callState: 'idle' },
    connecting: { text: 'Connecting...',  color: '#f59e0b', avatarAnim: 'pulse',  showEnd: false, showCall: true,  callState: 'connecting' },
    ringing:    { text: 'Ringing...',     color: '#f59e0b', avatarAnim: 'ring',   showEnd: true,  showCall: false, callState: 'connecting' },
    active:     { text: 'Connected',      color: '#22c55e', avatarAnim: 'breathe',showEnd: true,  showCall: false, callState: 'active' },
    ended:      { text: 'Call ended',     color: '#ef4444', avatarAnim: '',       showEnd: false, showCall: true,  callState: 'idle' },
    error:      { text: detail || 'Error',color: '#ef4444', avatarAnim: '',       showEnd: false, showCall: true,  callState: 'idle' },
  };

  const c = config[state] || config.idle;

  if (statusEl) {
    statusEl.textContent = c.text;
    statusEl.style.color = c.color;
  }
  if (avatarEl) avatarEl.setAttribute('data-anim', c.avatarAnim);
  if (callBtn) {
    callBtn.setAttribute('data-state', c.callState);
    callBtn.classList.toggle('hidden', !c.showCall);
  }
  if (endBtn)  endBtn.classList.toggle('hidden', !c.showEnd);
  if (muteBtn) muteBtn.classList.toggle('hidden', !c.showEnd);

  // Reset timer on non-active states
  if (state !== 'active' && state !== 'ringing' && state !== 'connecting') {
    if (timerEl) timerEl.textContent = '';
  }

  // Reset mode indicator
  if (modeEl && state !== 'active') {
    modeEl.textContent = '';
    modeEl.removeAttribute('data-mode');
  }

  // Clear error after 4s
  if (state === 'error' || state === 'ended') {
    setTimeout(() => {
      if (currentMode === state) setCallState('idle');
    }, 4000);
  }

  // Waveform
  if (state === 'active') {
    startWaveform();
  } else if (state === 'idle' || state === 'ended' || state === 'error') {
    stopWaveform();
  }
}

function updateAgentMode(mode) {
  // mode: 'speaking' | 'listening'
  const modeEl = $('mode-indicator');
  if (modeEl) {
    modeEl.textContent = mode === 'speaking' ? '● Agent Speaking' : '● Listening';
    modeEl.setAttribute('data-mode', mode);
  }
}

// ================================================================
//  5. TIMER
// ================================================================

function startTimer() {
  timerSeconds = 0;
  updateTimerDisplay();
  timerInterval = setInterval(() => {
    timerSeconds++;
    updateTimerDisplay();
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

function updateTimerDisplay() {
  const el = $('call-timer');
  if (!el) return;
  const m = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
  const s = String(timerSeconds % 60).padStart(2, '0');
  el.textContent = `${m}:${s}`;
}

// ================================================================
//  6. WAVEFORM VISUALIZER
// ================================================================

const WAVE_BARS = 40;
const barHeights = new Float32Array(WAVE_BARS);
const barTargets = new Float32Array(WAVE_BARS);
let waveMode = 'idle'; // idle | listening | speaking

function startWaveform() {
  if (waveformRAF) return;
  drawWaveframe();
}

function stopWaveform() {
  if (waveformRAF) {
    cancelAnimationFrame(waveformRAF);
    waveformRAF = null;
  }
  // Clear canvas
  const canvas = $('waveform');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
}

function drawWaveframe() {
  const canvas = $('waveform');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Get current mode from the mode indicator
  const modeEl = $('mode-indicator');
  const isActive = modeEl && modeEl.getAttribute('data-mode');
  waveMode = isActive === 'speaking' ? 'speaking' : (isActive === 'listening' ? 'listening' : 'idle');

  const barWidth = (w / WAVE_BARS) * 0.65;
  const gap = (w / WAVE_BARS) * 0.35;

  for (let i = 0; i < WAVE_BARS; i++) {
    // Generate target heights based on mode
    if (waveMode === 'speaking') {
      // Larger, more dynamic bars when agent speaks
      barTargets[i] = 0.15 + Math.random() * 0.75;
    } else if (waveMode === 'listening') {
      // Subtle ambient movement
      barTargets[i] = 0.05 + Math.random() * 0.2;
    } else {
      // Very minimal
      barTargets[i] = 0.03 + Math.random() * 0.06;
    }

    // Smooth interpolation
    barHeights[i] += (barTargets[i] - barHeights[i]) * 0.15;

    const barH = barHeights[i] * h * 0.85;
    const x = i * (barWidth + gap) + gap / 2;
    const y = (h - barH) / 2;

    // Gradient per bar
    const gradient = ctx.createLinearGradient(x, y, x, y + barH);
    if (waveMode === 'speaking') {
      gradient.addColorStop(0, 'rgba(0, 212, 170, 0.9)');
      gradient.addColorStop(1, 'rgba(0, 136, 255, 0.6)');
    } else if (waveMode === 'listening') {
      gradient.addColorStop(0, 'rgba(0, 136, 255, 0.5)');
      gradient.addColorStop(1, 'rgba(0, 136, 255, 0.2)');
    } else {
      gradient.addColorStop(0, 'rgba(136, 146, 164, 0.25)');
      gradient.addColorStop(1, 'rgba(136, 146, 164, 0.1)');
    }

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.roundRect(x, y, barWidth, barH, 2);
    ctx.fill();
  }

  waveformRAF = requestAnimationFrame(drawWaveframe);
}

// ================================================================
//  7. TOOL ACTIVITY LOG
// ================================================================

function logTool(icon, name, data, status) {
  const feed = $('tool-activity');
  if (!feed) return;

  const time = timeStr();
  const statusIcon = status === 'pending' ? '⏳' : (status === 'error' ? '✗' : '✓');
  const summary = typeof data === 'object' ? JSON.stringify(data) : String(data);
  const truncated = summary.length > 80 ? summary.slice(0, 77) + '...' : summary;

  // Check if there's a pending entry for this tool to update
  if (status === 'done' || status === 'error') {
    const pending = feed.querySelector(`.tool-entry[data-tool="${name}"][data-status="pending"]`);
    if (pending) {
      pending.setAttribute('data-status', status);
      pending.querySelector('.tool-entry-icon').textContent = statusIcon;
      pending.querySelector('.tool-entry-result').textContent = truncated;
      return;
    }
  }

  const entry = document.createElement('div');
  entry.className = 'tool-entry';
  entry.setAttribute('data-tool', name);
  entry.setAttribute('data-status', status);
  entry.innerHTML = `
    <span class="tool-entry-icon">${status === 'pending' ? icon : statusIcon}</span>
    <div class="tool-entry-body">
      <span class="tool-entry-name">${name}</span>
      <span class="tool-entry-time">${time}</span>
      <span class="tool-entry-result">${status === 'pending' ? 'Processing...' : truncated}</span>
    </div>
  `;

  feed.appendChild(entry);
  feed.scrollTop = feed.scrollHeight;

  // Keep max 20 entries
  while (feed.children.length > 20) {
    feed.removeChild(feed.firstChild);
  }
}

// ================================================================
//  8. PANEL TOGGLE
// ================================================================

function togglePanel() {
  const widget = $('phone-widget');
  const panel = $('phone-panel');
  if (!widget || !panel) return;

  const isExpanded = widget.getAttribute('data-state') === 'expanded';

  if (isExpanded) {
    panel.classList.add('hidden');
    widget.setAttribute('data-state', 'collapsed');
  } else {
    panel.classList.remove('hidden');
    widget.setAttribute('data-state', 'expanded');
    // Lazy-load config only when the user opens the voice UI.
    if (AGENT_ID === DEFAULT_AGENT_ID && !agentConfigPromise) {
      ensureAgentId().catch(() => {});
    }
  }

  syncVoiceBackdrop();
}

// ================================================================
//  9. MUTE TOGGLE
// ================================================================

let isMuted = false;

function toggleMute() {
  if (!conversation) return;
  isMuted = !isMuted;

  const muteBtn = $('btn-mute');
  if (muteBtn) {
    muteBtn.setAttribute('data-active', String(isMuted));
    muteBtn.innerHTML = isMuted
      ? '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .76-.12 1.5-.35 2.18"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>'
      : '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>';
  }

  // ElevenLabs SDK mute — attempt to set volume
  // The SDK handles mute via the session; we can try setVolume or similar
  // For now we track UI state; actual mute depends on SDK version
  if (conversation.setVolume) {
    conversation.setVolume({ volume: isMuted ? 0 : 1 });
  }
}

// ================================================================
//  10. INITIALIZATION
// ================================================================

function init() {
  if (voiceUiInitialized) return;
  voiceUiInitialized = true;

  const fab = $('phone-fab');
  const callBtn = $('btn-call');
  const endBtn = $('btn-end');
  const muteBtn = $('btn-mute');

  if (fab)     fab.addEventListener('click', togglePanel);
  if (callBtn) callBtn.addEventListener('click', startCall);
  if (endBtn)  endBtn.addEventListener('click', endCall);
  if (muteBtn) muteBtn.addEventListener('click', toggleMute);

  // Close panel when clicking outside
  document.addEventListener('click', (e) => {
    const widget = $('phone-widget');
    if (widget && widget.getAttribute('data-state') === 'expanded') {
      if (!widget.contains(e.target)) {
        togglePanel();
      }
    }
  });

  // Set initial state
  setCallState('idle');

  // Set canvas resolution for HiDPI
  const canvas = $('waveform');
  if (canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    // Restore logical drawing size
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
  }

  console.log('[VoiceAgent] Phone UI initialized');
  syncVoiceBackdrop();
}

// Run when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
