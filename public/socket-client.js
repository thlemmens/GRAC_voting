// socket-client.js — shared Socket.io client utilities
// Flask-SocketIO requires the v4 client served from /socket.io/socket.io.js
const socket = io({ transports: ['websocket', 'polling'] });

// ── Toast notification ─────────────────────────────────────────────────────────
function showToast(msg, duration = 2800) {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('show'), duration);
}

// ── Storage helpers ────────────────────────────────────────────────────────────
function saveLocal(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {}
}
function loadLocal(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch (_) { return null; }
}
