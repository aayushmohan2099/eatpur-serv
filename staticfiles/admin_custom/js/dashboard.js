/* ============================================================
   MILLET ADMIN — dashboard.js
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {

  // ---- Sidebar toggle ----
  const toggleBtn = document.getElementById('toggleSidebar');
  const sidebar   = document.getElementById('sidebar');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
      sidebar.classList.add('collapsed');
    }
  }

  // ---- Active sidebar link from current URL ----
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

  // ---- AJAX sidebar navigation ----
  document.querySelectorAll('.nav-item[data-href]').forEach(link => {
    link.addEventListener('click', function (e) {
      const href = this.getAttribute('data-href');
      if (!href) return;
      e.preventDefault();
      document.querySelectorAll('.nav-item').forEach(l => l.classList.remove('active'));
      this.classList.add('active');
      loadSection(href);
      history.pushState({}, '', href);
    });
  });

  // Handle browser back/forward
  window.addEventListener('popstate', () => {
    loadSection(window.location.pathname);
  });

});

function initDynamicContent() {
  // Re-run any chart or table init on dynamically loaded content
  if (typeof initTables === 'function') initTables();
}