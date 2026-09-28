/* Filter within a field with OR, across fields with AND. No dependencies. */
(() => {
  const table = document.getElementById('results');
  const rows = Array.from(table.tBodies[0].rows);
  const groups = Array.from(document.querySelectorAll('[data-filter]'));
  const defaults = new Map(groups.flatMap(group => Array.from(group.querySelectorAll('[data-value]'))
    .map(button => [button, button.getAttribute('aria-pressed')])));
  const leads = new Map(rows.map(row => [row, JSON.parse(row.dataset.leads)]));
  const count = document.getElementById('result-count');
  const empty = document.getElementById('no-results');
  function applyFilters() {
    const selected = Object.fromEntries(groups.map(group => [group.dataset.filter,
      new Set(Array.from(group.querySelectorAll('[data-value][aria-pressed="true"]')).map(button => button.dataset.value))]));
    groups.forEach(group => {
      const allSelected = selected[group.dataset.filter].size === group.querySelectorAll('[data-value]').length;
      const action = allSelected ? 'Clear' : 'All';
      const button = group.querySelector('.filter-all');
      button.textContent = action;
      button.setAttribute('aria-label', `${allSelected ? 'Clear' : 'Select'} all ${group.querySelector('legend').textContent} filters`);
    });
    let visible = 0;
    rows.forEach(row => {
      const matches = selected.verdict.has(row.dataset.verdict) && selected.genre.has(row.dataset.genre)
        && leads.get(row).some(lead => selected.attribution.has(lead.attribution) && selected.prior.has(lead.prior));
      row.hidden = !matches;
      if (matches) visible++;
    });
    count.textContent = `${visible} of ${rows.length} copies · Select bubbles to combine filters. Bubble counts are totals across all reviewed copies.`;
    empty.hidden = visible !== 0;
  }
  groups.forEach(group => {
    group.addEventListener('click', event => {
      const button = event.target.closest('button');
      if (!button) return;
      if (button.classList.contains('filter-all')) {
        const options = Array.from(group.querySelectorAll('[data-value]'));
        const allSelected = options.every(option => option.getAttribute('aria-pressed') === 'true');
        options.forEach(option => option.setAttribute('aria-pressed', String(!allSelected)));
      } else if (button.hasAttribute('data-value')) {
        button.setAttribute('aria-pressed', String(button.getAttribute('aria-pressed') !== 'true'));
      }
      applyFilters();
    });
  });
  document.getElementById('reset-filters').addEventListener('click', () => {
    defaults.forEach((value, button) => button.setAttribute('aria-pressed', value));
    applyFilters();
  });
  applyFilters();
  document.getElementById('filters').hidden = false;
  document.getElementById('reset-filters').hidden = false;

  document.querySelectorAll('table.sortable th[data-col]').forEach(th => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'sort-button';
    button.textContent = th.textContent;
    button.setAttribute('aria-label', `Sort by ${th.textContent}`);
    th.replaceChildren(button);
    button.addEventListener('click', () => {
      const owner = th.closest('table'), body = owner.tBodies[0], column = Number(th.dataset.col);
      const ascending = th.getAttribute('aria-sort') !== 'ascending';
      owner.querySelectorAll('[aria-sort]').forEach(header => header.removeAttribute('aria-sort'));
      th.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
      const value = row => row.cells[column].dataset.sort ?? row.cells[column].textContent.trim();
      const ordered = Array.from(body.rows).sort((a, b) => {
        const x = value(a), y = value(b);
        const comparison = th.dataset.type === 'number' ? Number(x) - Number(y) : x.localeCompare(y, undefined, {numeric:true});
        return comparison * (ascending ? 1 : -1);
      });
      ordered.forEach(row => body.appendChild(row));
    });
  });
})();
