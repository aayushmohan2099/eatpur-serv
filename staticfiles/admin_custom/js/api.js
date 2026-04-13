/* ============================================================
   MILLET ADMIN — api.js
   Centralised fetch helpers. All views return JSON on AJAX,
   partial HTML on X-Requested-With: XMLHttpRequest.
   ============================================================ */

function getCookie(name) {
  let value = null;
  document.cookie.split(';').forEach(c => {
    const [k, v] = c.trim().split('=');
    if (k === name) value = decodeURIComponent(v);
  });
  return value;
}

const CSRF = () => getCookie('csrftoken');

/* ---- Section loader ---- */
async function loadSection(url, targetSelector = '#mainContent') {
  const target = document.querySelector(targetSelector);
  if (!target) return;
  target.innerHTML = '<div class="loading-spinner"></div>';
  try {
    const res = await fetch(url, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const html = await res.text();
    target.innerHTML = html;
    initDynamicContent();
    // Re-run any inline scripts in the loaded HTML
    target.querySelectorAll('script').forEach(old => {
      const s = document.createElement('script');
      s.textContent = old.textContent;
      old.parentNode.replaceChild(s, old);
    });
  } catch (err) {
    target.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><h3>Failed to load</h3><p>${err.message}</p></div>`;
  }
}

/* ---- Generic API calls ---- */
async function apiGet(url) {
  const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
  return res.json();
}

async function apiPost(url, data = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': CSRF(),
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(data),
  });
  return res.json();
}

async function apiPatch(url, data = {}) {
  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': CSRF(),
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(data),
  });
  return res.json();
}

async function apiDelete(url) {
  const res = await fetch(url, {
    method: 'DELETE',
    headers: {
      'X-CSRFToken': CSRF(),
      'X-Requested-With': 'XMLHttpRequest',
    },
  });
  return res.json();
}

/* ---- Form submit via fetch ---- */
async function submitForm(formEl, url, method = 'POST') {
  const fd = new FormData(formEl);
  const res = await fetch(url, {
    method,
    headers: { 'X-CSRFToken': CSRF(), 'X-Requested-With': 'XMLHttpRequest' },
    body: fd,
  });
  return res.json();
}

/* ---- Toast notification ---- */
function toast(message, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  Object.assign(el.style, {
    position: 'fixed', bottom: '24px', right: '24px', zIndex: '9999',
    padding: '12px 20px', borderRadius: '8px', fontSize: '13px', fontWeight: '500',
    background: type === 'success' ? '#15803d' : type === 'error' ? '#dc2626' : '#b45309',
    color: '#fff', boxShadow: '0 4px 12px rgba(0,0,0,.2)',
    transform: 'translateY(20px)', opacity: '0',
    transition: 'all .25s cubic-bezier(.4,0,.2,1)',
  });
  document.body.appendChild(el);
  requestAnimationFrame(() => { el.style.transform = 'translateY(0)'; el.style.opacity = '1'; });
  setTimeout(() => {
    el.style.opacity = '0'; el.style.transform = 'translateY(20px)';
    setTimeout(() => el.remove(), 300);
  }, 3000);
}