/* ============================================================
   MILLET ADMIN — tables.js
   ============================================================ */

function initTables() {
  document.querySelectorAll('[data-table]').forEach(table => {
    const searchInput = document.querySelector(`[data-table-search="${table.dataset.table}"]`);
    const tbody = table.querySelector('tbody');
    if (!tbody) return;
    const perPage = parseInt(table.dataset.perPage || '20');
    let allRows = Array.from(tbody.querySelectorAll('tr:not(.skeleton-row)'));
    let filtered = allRows;
    let currentPage = 1;
    let sortCol = -1, sortAsc = true;

    // Search
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        const q = searchInput.value.toLowerCase();
        filtered = allRows.filter(r => r.textContent.toLowerCase().includes(q));
        currentPage = 1;
        render();
      });
    }

    // Sort headers
    table.querySelectorAll('thead th[data-col]').forEach(th => {
      th.addEventListener('click', () => {
        const col = parseInt(th.dataset.col);
        if (sortCol === col) sortAsc = !sortAsc;
        else { sortCol = col; sortAsc = true; }
        table.querySelectorAll('thead th').forEach(h => h.classList.remove('sorted'));
        th.classList.add('sorted');
        th.querySelector('.sort-arrow').textContent = sortAsc ? ' ↑' : ' ↓';
        filtered.sort((a, b) => {
          const at = a.cells[col]?.textContent.trim() || '';
          const bt = b.cells[col]?.textContent.trim() || '';
          return sortAsc ? at.localeCompare(bt, undefined, {numeric:true}) : bt.localeCompare(at, undefined, {numeric:true});
        });
        currentPage = 1;
        render();
      });
    });

    function render() {
      const start = (currentPage - 1) * perPage;
      const visible = filtered.slice(start, start + perPage);
      allRows.forEach(r => { r.style.display = 'none'; });
      visible.forEach(r => { r.style.display = ''; });
      renderPagination();
    }

    function renderPagination() {
      const container = document.querySelector(`[data-table-pagination="${table.dataset.table}"]`);
      if (!container) return;
      const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
      let html = `<button class="pagination-btn" onclick="goPage('${table.dataset.table}',${currentPage-1})" ${currentPage===1?'disabled':''}>‹</button>`;
      for (let i = 1; i <= totalPages; i++) {
        html += `<button class="pagination-btn ${i===currentPage?'active':''}" onclick="goPage('${table.dataset.table}',${i})">${i}</button>`;
      }
      html += `<button class="pagination-btn" onclick="goPage('${table.dataset.table}',${currentPage+1})" ${currentPage===totalPages?'disabled':''}>›</button>`;
      container.innerHTML = html;
    }

    window[`goPage_${table.dataset.table}`] = function(page) {
      currentPage = page;
      render();
    };

    render();
  });
}

function goPage(tableId, page) {
  const fn = window[`goPage_${tableId}`];
  if (fn) fn(page);
}

document.addEventListener('DOMContentLoaded', initTables);