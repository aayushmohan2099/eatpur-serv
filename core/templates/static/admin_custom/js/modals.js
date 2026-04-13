/* ============================================================
   MILLET ADMIN — modals.js
   ============================================================ */

const overlay   = document.getElementById('modalOverlay');
const container = document.getElementById('modalContainer');

function openModal(title, bodyHTML, footerHTML = '', opts = {}) {
  container.className = `modal-container ${opts.size || ''}`;
  container.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">${title}</span>
        <button class="modal-close" onclick="closeModal()">×</button>
      </div>
      <div class="modal-body">${bodyHTML}</div>
      ${footerHTML ? `<div class="modal-footer">${footerHTML}</div>` : ''}
    </div>`;
  overlay.classList.add('open');
  container.classList.add('open');
  document.addEventListener('keydown', _escHandler);
}

function closeModal() {
  overlay.classList.remove('open');
  container.classList.remove('open');
  document.removeEventListener('keydown', _escHandler);
  setTimeout(() => { container.innerHTML = ''; }, 200);
}

function _escHandler(e) { if (e.key === 'Escape') closeModal(); }

/* ---- Confirm delete modal ---- */
function confirmDelete(label, onConfirm) {
  openModal(
    '⚠️ Confirm Delete',
    `<p style="font-size:14px;color:var(--text)">Are you sure you want to delete <strong>${label}</strong>? This action cannot be undone.</p>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
     <button class="btn btn-danger" id="confirmDeleteBtn">Delete</button>`,
    { size: 'narrow' }
  );
  document.getElementById('confirmDeleteBtn').addEventListener('click', async () => {
    document.getElementById('confirmDeleteBtn').textContent = 'Deleting…';
    await onConfirm();
    closeModal();
  });
}

/* ---- View detail modal ---- */
function viewModal(title, rows) {
  // rows: [{label, value}]
  const rowsHTML = rows.map(r => `
    <div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;">
      <span style="color:var(--text-muted);font-weight:500;">${r.label}</span>
      <span style="color:var(--text);text-align:right;max-width:60%;">${r.value}</span>
    </div>`).join('');
  openModal(title, rowsHTML, `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`);
}