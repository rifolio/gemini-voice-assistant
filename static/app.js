const statusDot    = document.querySelector("#statusDot");
const statusText   = document.querySelector("#statusText");
const transcript   = document.querySelector("#transcript");
const toolStream   = document.querySelector("#toolStream");
const toolCount    = document.querySelector("#toolCount");
const messageForm  = document.querySelector("#messageForm");
const messageInput = document.querySelector("#messageInput");
const systemPrompt = document.querySelector("#systemPrompt");
const voiceSelect  = document.querySelector("#voiceSelect");
const previewBtn   = document.querySelector("#previewBtn");
const previewIcon  = document.querySelector("#previewIcon");
const startButton  = document.querySelector("#startButton");
const stopButton   = document.querySelector("#stopButton");
const micButton    = document.querySelector("#micButton");

// ── Persist voice + prompt to localStorage ─────────────────
const LS_VOICE  = "rifo_voice";
const LS_PROMPT = "rifo_prompt_sandra_v1";
const LEGACY_PROMPT_KEYS = ["rifo_prompt"];
const SANDRA_PROMPT_MARKER = "# Sandra";

function loadPrefs() {
  const savedVoice  = localStorage.getItem(LS_VOICE);
  const savedPrompt = localStorage.getItem(LS_PROMPT);
  if (savedVoice)  voiceSelect.value  = savedVoice;
  LEGACY_PROMPT_KEYS.forEach((key) => localStorage.removeItem(key));
  if (savedPrompt && savedPrompt.startsWith(SANDRA_PROMPT_MARKER)) {
    systemPrompt.value = savedPrompt;
  } else {
    localStorage.removeItem(LS_PROMPT);
  }
}

systemPrompt.addEventListener("input", () => {
  localStorage.setItem(LS_PROMPT, systemPrompt.value);
});

loadPrefs();

// ── Voice preview ─────────────────────────────────────────────
const PLAY_ICON = `<polygon points="5 3 19 12 5 21 5 3"/>`;
const STOP_ICON = `<rect x="5" y="5" width="14" height="14" rx="2"/>`;

let previewAudio = null;

function setPreviewPlaying(playing) {
  previewBtn.classList.toggle("playing", playing);
  previewIcon.innerHTML = playing ? STOP_ICON : PLAY_ICON;
}

voiceSelect.addEventListener("change", () => {
  localStorage.setItem(LS_VOICE, voiceSelect.value);
  if (previewAudio && !previewAudio.paused) {
    previewAudio.pause();
    setPreviewPlaying(false);
  }
});

previewBtn.addEventListener("click", () => {
  if (previewAudio && !previewAudio.paused) {
    previewAudio.pause();
    previewAudio.currentTime = 0;
    setPreviewPlaying(false);
    return;
  }
  const voice = voiceSelect.value.toLowerCase();
  previewAudio = new Audio(`/static/voices/${voice}.wav`);
  previewAudio.addEventListener("ended", () => setPreviewPlaying(false));
  previewAudio.addEventListener("error", () => {
    setPreviewPlaying(false);
    setStatus("Voice sample not found", "error");
  });
  previewAudio.play();
  setPreviewPlaying(true);
});

let socket        = null;
let playCtx       = null;   // AudioContext for playback (24 kHz)
let nextPlayTime  = 0;
let micStream     = null;
let micCtx        = null;   // AudioContext for capture (16 kHz)
let micProcessor  = null;
let isListening   = false;
let toolCallCount = 0;

// ── Status ────────────────────────────────────────────────────
function setStatus(text, state = "") {
  statusText.textContent = text;
  statusDot.className = "status-dot " + state;
}

// ── Transcript ────────────────────────────────────────────────
function hideEmpty() {
  const el = document.querySelector("#emptyState");
  if (el) el.remove();
}

function addMessage(role, text) {
  hideEmpty();

  // For voice transcripts, append to last bubble of same role if it's recent
  const last = transcript.lastElementChild;
  if (
    last &&
    last.classList.contains(role) &&
    last.dataset.voice === "1"
  ) {
    last.querySelector(".message-bubble").textContent += " " + text;
    transcript.scrollTop = transcript.scrollHeight;
    return;
  }

  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Agent";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  wrap.dataset.voice = "1";  // mark all voice transcript bubbles so chunks merge
  wrap.append(label, bubble);
  transcript.appendChild(wrap);
  transcript.scrollTop = transcript.scrollHeight;
}

// ── Tool events ───────────────────────────────────────────────
function addToolEvent(type, name, payload) {
  const placeholder = toolStream.querySelector(".tool-empty");
  if (placeholder) placeholder.remove();

  toolCallCount++;
  toolCount.textContent = toolCallCount;
  toolCount.hidden = false;

  const item = document.createElement("div");
  item.className = "tool-event";

  const title = document.createElement("div");
  title.className = "tool-event-title";

  const tag = document.createElement("span");
  tag.className = `tag tag-${type}`;
  tag.textContent = type === "call" ? "call" : type === "error" ? "error" : "result";

  title.append(tag, document.createTextNode(" " + name));

  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(payload, null, 2);

  item.append(title, pre);
  toolStream.prepend(item);
}

// ── Playback audio ────────────────────────────────────────────
function ensurePlayCtx() {
  if (!playCtx) {
    playCtx = new AudioContext({ sampleRate: 24000 });
    nextPlayTime = playCtx.currentTime;
  }
  return playCtx;
}

function b64ToInt16(value) {
  const bin = atob(value);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Int16Array(bytes.buffer);
}

function playPcm(dataBase64, sampleRate) {
  const ctx = ensurePlayCtx();
  const samples = b64ToInt16(dataBase64);
  const buf = ctx.createBuffer(1, samples.length, sampleRate);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < samples.length; i++) ch[i] = samples[i] / 32768;
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.connect(ctx.destination);
  const startAt = Math.max(ctx.currentTime, nextPlayTime);
  src.start(startAt);
  nextPlayTime = startAt + buf.duration;
}

// ── Microphone capture ────────────────────────────────────────
async function startMic() {
  if (isListening) return;
  try {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  } catch (e) {
    setStatus("Mic denied: " + e.message, "error");
    return;
  }

  // Capture at 16 kHz (what Gemini Live expects for input PCM)
  micCtx = new AudioContext({ sampleRate: 16000 });
  const source = micCtx.createMediaStreamSource(micStream);
  micProcessor = micCtx.createScriptProcessor(4096, 1, 1);

  micProcessor.onaudioprocess = (ev) => {
    if (!isListening || !socket || socket.readyState !== WebSocket.OPEN) return;
    const floats = ev.inputBuffer.getChannelData(0);
    const int16 = new Int16Array(floats.length);
    for (let i = 0; i < floats.length; i++) {
      int16[i] = Math.max(-32768, Math.min(32767, Math.round(floats[i] * 32767)));
    }
    socket.send(JSON.stringify({
      type: "user_audio",
      data_base64: uint8ToB64(new Uint8Array(int16.buffer)),
    }));
  };

  source.connect(micProcessor);
  micProcessor.connect(micCtx.destination);
  isListening = true;
  micButton.classList.add("listening");
  micButton.setAttribute("aria-label", "Stop speaking");
  setStatus("Listening…", "connected");
}

function stopMic() {
  if (!isListening) return;
  isListening = false;
  micButton.classList.remove("listening");
  micButton.setAttribute("aria-label", "Hold to speak");
  if (socket && socket.readyState === WebSocket.OPEN) {
    setStatus("Connected", "connected");
  }
  if (micProcessor) { micProcessor.disconnect(); micProcessor = null; }
  if (micCtx)       { micCtx.close();           micCtx = null; }
  if (micStream)    { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
}

function uint8ToB64(bytes) {
  let bin = "";
  const chunk = 8192;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}

// ── WebSocket ─────────────────────────────────────────────────
function openSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) return socket;

  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws`);

  socket.addEventListener("message", (ev) => {
    const p = JSON.parse(ev.data);

    if (p.type === "session_status") {
      const connected = p.status === "connected";
      setStatus(connected ? "Connected" : p.status, connected ? "connected" : "");

    } else if (p.type === "transcript") {
      // Show both user voice transcripts and assistant transcripts
      addMessage(p.role, p.text);

    } else if (p.type === "audio_chunk") {
      try { playPcm(p.data_base64, p.sample_rate); }
      catch (e) { setStatus("Audio error: " + e.message, "error"); }

    } else if (p.type === "tool_call") {
      addToolEvent("call", p.name, p.args);

    } else if (p.type === "tool_result") {
      addToolEvent(p.status === "error" ? "error" : "result", p.status, p.result);

    } else if (p.type === "error") {
      setStatus(p.message, "error");

    } else if (p.type === "hang_up") {
      stopMic();
      setStatus("Agent hung up", "");
      addMessage("assistant", p.message || "The agent has ended the call.");
      if (socket) { socket.close(); socket = null; }
    }
  });

  socket.addEventListener("close", () => {
    stopMic();
    setStatus("Disconnected", "");
  });
  socket.addEventListener("error", () => setStatus("Connection error", "error"));
  return socket;
}

// ── Session controls ──────────────────────────────────────────
startButton.addEventListener("click", () => {
  // Clear previous conversation
  transcript.innerHTML = "";
  toolStream.innerHTML = '<p class="tool-empty">No tool calls yet</p>';
  toolCallCount = 0;
  toolCount.hidden = true;

  const empty = document.createElement("div");
  empty.id = "emptyState";
  empty.className = "empty-state";
  empty.innerHTML = `
    <div class="empty-icon">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    </div>
    <p class="empty-title">Session started</p>
    <p class="empty-hint">Press the mic button or type below.</p>`;
  transcript.appendChild(empty);

  setStatus("Connecting…", "");
  const s = openSocket();

  const sendStart = () => s.send(JSON.stringify({
    type: "start_session",
    system_prompt: systemPrompt.value.trim(),
    voice: voiceSelect.value,
  }));

  if (s.readyState === WebSocket.OPEN) sendStart();
  else s.addEventListener("open", sendStart, { once: true });
});

stopButton.addEventListener("click", () => {
  stopMic();
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "stop_session" }));
    socket.close();
  }
  setStatus("Stopped", "");
});

// ── Mic toggle ────────────────────────────────────────────────
micButton.addEventListener("click", async () => {
  if (isListening) {
    stopMic();
  } else {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setStatus("Start a session first", "error");
      return;
    }
    await startMic();
  }
});

// ── Text submit ───────────────────────────────────────────────
messageForm.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;

  // Optimistic display — text input is never echoed back by the backend
  addMessage("user", text);
  messageInput.value = "";

  if (!socket || socket.readyState !== WebSocket.OPEN) {
    setStatus("Start a session first", "error");
    return;
  }
  socket.send(JSON.stringify({ type: "user_text", text }));
});
