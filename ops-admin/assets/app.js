/* ============================================================
   DRB Ops Admin — UI interactions
   ============================================================ */

(() => {
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  // ---- Router ----
  function showRoute(hash) {
    const route = (hash || location.hash || '#/jobs').replace(/^#/, '');
    $$('[data-route]').forEach(el => {
      el.hidden = el.dataset.route !== route;
    });
    $$('.sidebar__item').forEach(el => {
      el.classList.toggle('sidebar__item--active', el.dataset.routeLink === route);
    });
    const page = $(`[data-route="${route}"]`);
    if (page) {
      const title = page.dataset.pageTitle || '';
      const crumb = page.dataset.pageCrumb || '';
      const titleEl = $('.topbar__title');
      const crumbEl = $('.topbar__breadcrumb-current');
      if (titleEl) titleEl.textContent = title;
      if (crumbEl) crumbEl.textContent = crumb;
    }
    closeDrawer();
  }

  window.addEventListener('hashchange', () => showRoute());
  $$('.sidebar__item').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const target = el.dataset.routeLink;
      if (target) {
        location.hash = '#' + target;
      }
    });
  });

  // ---- Drawer ----
  function openDrawer(id) {
    const ws = $('.workspace');
    if (!ws) return;
    $$('[data-drawer]').forEach(d => d.hidden = d.dataset.drawer !== id);
    ws.classList.add('workspace--with-drawer');
  }
  function closeDrawer() {
    const ws = $('.workspace');
    if (!ws) return;
    ws.classList.remove('workspace--with-drawer');
    $$('[data-drawer]').forEach(d => d.hidden = true);
    $$('.table tr.selected').forEach(tr => tr.classList.remove('selected'));
  }
  window.openDrawer = openDrawer;
  window.closeDrawer = closeDrawer;

  document.addEventListener('click', (e) => {
    const row = e.target.closest('tr[data-row-drawer]');
    if (row) {
      $$('.table tr.selected').forEach(tr => tr.classList.remove('selected'));
      row.classList.add('selected');
      openDrawer(row.dataset.rowDrawer);
      return;
    }
    const closeBtn = e.target.closest('[data-drawer-close]');
    if (closeBtn) closeDrawer();

    const tabBtn = e.target.closest('[data-tab-group]');
    if (tabBtn) {
      const group = tabBtn.dataset.tabGroup;
      $$(`[data-tab-group="${group}"]`).forEach(t => t.classList.remove('drawer__tab--active', 'subbar__tab--active'));
      const cls = tabBtn.classList.contains('subbar__tab') ? 'subbar__tab--active' : 'drawer__tab--active';
      tabBtn.classList.add(cls);
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawer();
  });

  // ---- Live clock (ops feel) ----
  const clockEl = $('#live-clock');
  if (clockEl) {
    const tick = () => {
      const d = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      clockEl.textContent = `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} UTC`;
    };
    tick();
    setInterval(tick, 1000);
  }

  // ---- Init ----
  showRoute(location.hash || '#/jobs');
})();
