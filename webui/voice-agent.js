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

async function ensureAgentId() {
  if (AGENT_ID && AGENT_ID !== DEFAULT_AGENT_ID) return AGENT_ID;
  if (agentConfigPromise) return agentConfigPromise;

  const apiBase = getApiBase();
  agentConfigPromise = (async () => {
    try {
      const res = await fetch(`${apiBase}/tools/VoiceAgent/config`);
      if (!res.ok) throw new Error(`Config request failed (${res.status})`);

      const data = await res.json();
      const candidate = String(data?.agent_id || '').trim();
      if (candidate) {
        AGENT_ID = candidate;
      }
      return AGENT_ID;
    } catch (err) {
      console.warn('[VoiceAgent] Failed to load AGENT_ID from backend config:', err);
      return AGENT_ID;
    }
  })();

  return agentConfigPromise;
}

// ── State ───────────────────────────────────────────────────
let conversation = null;
let timerInterval = null;
let timerSeconds = 0;
let currentMode = 'idle'; // idle | connecting | ringing | active | ended | error
let waveformRAF = null;

// ── DOM refs (populated in init) ────────────────────────────
const $ = (id) => document.getElementById(id);

// ── Helpers ─────────────────────────────────────────────────
function getApiBase() {
  const el = $('apiBase');
  return el ? el.value.trim().replace(/\/+$/, '') : 'http://127.0.0.1:8000';
}

function timeStr() {
  return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ================================================================
//  1. SESSION LIFECYCLE
// ================================================================

async function startCall() {
  if (conversation) return;

  await ensureAgentId();

  if (AGENT_ID === DEFAULT_AGENT_ID) {
    setCallState('error', 'Set ELEVENLABS_AGENT_ID in .env and restart backend');
    return;
  }

  try {
    setCallState('connecting');

    // Load SDK if not loaded
    await loadSDK();

    // Request microphone
    await navigator.mediaDevices.getUserMedia({ audio: true });
    setCallState('ringing');

    conversation = await Conversation.startSession({
      agentId: AGENT_ID,
      clientTools: buildClientTools(),
      onConnect: () => {
        setCallState('active');
        startTimer();
      },
      onDisconnect: () => {
        setCallState('ended');
        stopTimer();
        conversation = null;
      },
      onModeChange: ({ mode }) => {
        updateAgentMode(mode);
      },
      onError: (e) => {
        console.error('[VoiceAgent] Session error:', e);
        setCallState('error', 'Connection lost');
        stopTimer();
        conversation = null;
      },
    });
  } catch (err) {
    console.error('[VoiceAgent] Failed to start call:', err);
    const msg = err.name === 'NotAllowedError'
      ? 'Microphone access denied'
      : (err.message || 'Connection failed');
    setCallState('error', msg);
    conversation = null;
  }
}

async function endCall() {
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
      return JSON.stringify(data);
    } catch (err) {
      const errObj = { error: err.message };
      logTool(icon, endpoint, errObj, 'error');
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
    requestUpload: handleUploadRequest,
  };
}

// ================================================================
//  3. UPLOAD MODAL HANDLER (Tool 9)
// ================================================================

async function handleUploadRequest(params) {
  const { upload_type } = params; // "skin_image" | "lab_report" | "prescription"
  const API = getApiBase();
  const patientId = $('patientId')?.value?.trim() || '';
  const sessionId = $('sessionId')?.value?.trim() || '';

  const isSkin = upload_type === 'skin_image';
  const displayName = isSkin ? 'Skin Image' : upload_type.replace(/_/g, ' ');

  logTool('📸', 'requestUpload', { upload_type }, 'pending');

  const result = await new Promise((resolve) => {
    const modal = $('upload-modal');

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

    // ── Wire events ──
    const fileInput = $('upload-file');
    const cancelBtn = $('upload-cancel');

    cancelBtn.onclick = () => {
      modal.classList.add('hidden');
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
        const data = await res.json();

        // Success state
        progressFill.classList.remove('indeterminate');
        progressFill.style.width = '100%';
        progressText.textContent = '✓ Upload complete!';
        progressText.classList.add('success');

        // Auto-close
        setTimeout(() => { modal.classList.add('hidden'); }, 1500);

        resolve(JSON.stringify(data));
      } catch (err) {
        progressFill.classList.remove('indeterminate');
        progressText.textContent = '✗ Upload failed — ' + (err.message || 'Unknown error');
        progressText.classList.add('error');

        setTimeout(() => { modal.classList.add('hidden'); }, 2500);

        resolve(JSON.stringify({ error: err.message || 'Upload failed' }));
      }
    };
  });

  logTool('📸', 'requestUpload', JSON.parse(result), 'done');
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
  }
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
  ensureAgentId().then((loadedAgentId) => {
    if (loadedAgentId === DEFAULT_AGENT_ID) {
      console.warn('[VoiceAgent] Missing ELEVENLABS_AGENT_ID. Set it in .env and restart backend.');
    }
  });
}

// Run when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
