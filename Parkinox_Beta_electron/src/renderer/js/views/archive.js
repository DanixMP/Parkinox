import { h, faNum, faMoney, plateEl } from '../util.js';
import { icons } from '../icons.js';
import { store } from '../store.js';

export function renderArchive(navigate) {
  let filter = 'all';
  const tbody = h('tbody');

  const render = () => {
    let rows = store.archive;
    if (filter !== 'all') rows = rows.filter((r) => r.dir === filter);
    tbody.replaceChildren(...rows.map((r) => {
      const dirBadge = r.dir === 'entry'
        ? h('span', { class: 'badge', style: { background: 'rgba(34,197,94,.12)', border: '1px solid var(--green)', color: 'var(--green)' }, text: 'ورود' })
        : h('span', { class: 'badge', style: { background: 'rgba(239,68,68,.12)', border: '1px solid var(--red)', color: 'var(--red)' }, text: 'خروج' });
      const statusBadge = r.status === 'paid'
        ? h('span', { class: 'badge', style: { color: 'var(--green)' }, text: 'پرداخت‌شده' })
        : h('span', { class: 'badge', style: { color: 'var(--orange)' }, text: 'بدهکار' });
      return h('tr', {}, [
        h('td', {}, [plateEl(r.plate, { compact: true })]),
        h('td', {}, [dirBadge]),
        h('td', { text: faNum(r.time) }),
        h('td', { text: r.operator }),
        h('td', {}, [statusBadge]),
        h('td', { text: r.fee ? faMoney(r.fee) + ' ت' : '—' }),
      ]);
    }));
  };

  const chip = (label, val) => h('button', { class: 'chip' + (filter === val ? ' active' : ''), style: { flex: 'none', padding: '8px 16px' }, text: label,
    onClick: () => { filter = val; head.replaceChildren(...chips()); render(); } });
  const chips = () => [chip('همه', 'all'), chip('ورود', 'entry'), chip('خروج', 'exit')];
  const head = h('div', { style: { display: 'flex', gap: '8px' } }, chips());

  render();

  return h('div', { class: 'page' }, [
    h('div', { class: 'page-head' }, [
      h('button', { class: 'icon-btn', html: icons.back, onClick: () => navigate('dashboard') }),
      h('h1', { text: 'آرشیو و گزارش' }),
      h('div', { class: 'spacer', style: { flex: '1' } }),
      head,
    ]),
    h('div', { class: 'card', style: { padding: '8px' } }, [
      h('table', { class: 'table' }, [
        h('thead', {}, [h('tr', {}, [
          h('th', { text: 'پلاک' }), h('th', { text: 'جهت' }), h('th', { text: 'زمان' }),
          h('th', { text: 'اپراتور' }), h('th', { text: 'وضعیت' }), h('th', { text: 'هزینه' }),
        ])]),
        tbody,
      ]),
    ]),
  ]);
}
