import { h, faNum, faMoney, plateEl, toast, WEEKDAYS, toJalali } from '../util.js';
import { icons } from '../icons.js';
import { store, emit } from '../store.js';

// Module-level timers so we can clean up on navigation.
let clockTimer = null;
let detectTimer = null;
let countdownTimer = null;

export function disposeDashboard() {
  clearInterval(clockTimer); clockTimer = null;
  clearTimeout(detectTimer); detectTimer = null;
  clearInterval(countdownTimer); countdownTimer = null;
}

export function renderDashboard(navigate) {
  disposeDashboard();

  const root = h('div', { style: { display: 'flex', flexDirection: 'column', flex: '1', minHeight: '0' } });

  // ── Toolbar ──────────────────────────────────────────────
  const clockPill = h('div', { class: 'pill' });
  const statusPill = h('div', { class: 'pill clickable' });
  let statusExpanded = false;

  const renderStatus = () => {
    const all = store.health.fastApi && store.health.django && store.health.ws;
    const color = all ? 'var(--green)' : 'var(--red)';
    statusPill.innerHTML = '';
    statusPill.append(h('span', { class: 'dot', style: { background: color } }));
    if (statusExpanded) {
      const sp = (lbl, on) => h('span', { style: { display: 'inline-flex', alignItems: 'center', gap: '4px', color: on ? 'var(--green)' : 'var(--text-muted)' } }, [
        h('span', { class: 'dot', style: { width: '6px', height: '6px', background: on ? 'var(--green)' : 'var(--red)' } }), lbl,
      ]);
      statusPill.append(sp('FastAPI', store.health.fastApi), sp('Django', store.health.django), sp('WS', store.health.ws));
    }
  };
  statusPill.addEventListener('click', () => { statusExpanded = !statusExpanded; renderStatus(); });
  renderStatus();

  const updateClock = () => {
    const now = new Date();
    const t = [now.getHours(), now.getMinutes(), now.getSeconds()].map((n) => String(n).padStart(2, '0')).join(':');
    const [jy, jm, jd] = toJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
    const wd = WEEKDAYS[(now.getDay() + 1) % 7];
    const dateStr = `${faNum(jy)}/${faNum(String(jm).padStart(2, '0'))}/${faNum(String(jd).padStart(2, '0'))}`;
    clockPill.innerHTML = `${icons.calendar}<span>${wd}، ${dateStr}</span><span class="sep"></span>${icons.clock}<span>${faNum(t)}</span>`;
  };
  updateClock();
  clockTimer = setInterval(updateClock, 1000);

  const tbtn = (icon, tip, onClick) => h('button', { class: 'icon-btn', title: tip, html: icon, onClick });

  const toolbar = h('div', { class: 'toolbar' }, [
    h('div', { class: 'brand' }, [
      h('div', { class: 'brand-logo', html: icons.parking }),
      h('div', { class: 'brand-text' }, [
        h('span', { class: 'brand-name', text: 'پارکینوکس' }),
        h('span', { class: 'brand-role', text: 'پنل اپراتور' }),
      ]),
    ]),
    clockPill,
    statusPill,
    h('div', { class: 'spacer' }),
    store.activeOperator && h('div', { class: 'op-chip', text: store.activeOperator.name }),
    h('div', { class: 'toolbar-actions' }, [
      tbtn(icons.tools, 'ابزارها', () => toast('ابزارها — نسخه دمو', 'orange')),
      tbtn(icons.archive, 'آرشیو و گزارش', () => navigate('archive')),
      tbtn(icons.wallet, 'شارژ کیف پول', () => toast('شارژ کیف پول — نسخه دمو', 'orange')),
      tbtn(icons.settings, 'تنظیمات', () => navigate('settings')),
      tbtn(icons.logout, 'خروج', () => { store.activeOperator = null; emit(); disposeDashboard(); navigate('login'); }),
    ]),
  ]);

  // ── Stats ────────────────────────────────────────────────
  const statsBar = h('div', { class: 'stats' });
  const renderStats = () => {
    const parked = store.parked;
    const reg = parked.filter((p) => p.registered).length;
    const guest = parked.length - reg;
    const r = store.rates;
    const stat = (label, value, sub, accent) =>
      h('div', { class: 'stat', style: { '--accent': accent } }, [
        h('div', { class: 'stat-label', text: label }),
        h('div', { class: 'stat-value', text: value }),
        h('div', { class: 'stat-sub', text: sub }),
      ]);
    statsBar.replaceChildren(
      stat('پارک‌شده', faNum(parked.length), `${faNum(reg)} ثبت · ${faNum(guest)} مهمان`, 'var(--green)'),
      stat('منتظر پرداخت', faNum(store.unpaid.length), 'جلسه', 'var(--orange)'),
      stat('نرخ ساعتی', faMoney(r.ratePerHour), 'تومان / ساعت', 'var(--blue)'),
      stat('مهلت رایگان', faNum(r.gracePeriodMinutes), `سقف ${faMoney(r.dailyCap)}`, 'var(--purple)'),
    );
  };
  renderStats();

  // ── Side panels ──────────────────────────────────────────
  let parkedFilter = 'all';
  const leftList = h('div', { class: 'list' });
  const rightList = h('div', { class: 'list' });

  const renderParked = () => {
    let items = store.parked;
    if (parkedFilter === 'registered') items = items.filter((s) => s.registered);
    if (parkedFilter === 'guest') items = items.filter((s) => !s.registered);
    if (!items.length) { leftList.replaceChildren(h('div', { class: 'empty', text: 'پارکینگ خالی است' })); return; }
    leftList.replaceChildren(...items.map((s) => sessionCard(s, false, renderAll)));
  };
  const renderUnpaid = () => {
    if (!store.unpaid.length) { rightList.replaceChildren(h('div', { class: 'empty', text: 'بدون بدهی' })); return; }
    rightList.replaceChildren(...store.unpaid.map((s) => sessionCard(s, true, renderAll)));
  };

  const filterChip = (label, val) =>
    h('button', { class: 'chip' + (parkedFilter === val ? ' active' : ''), text: label,
      onClick: () => { parkedFilter = val; renderLeftHead(); renderParked(); } });

  const leftHead = h('div');
  const renderLeftHead = () => leftHead.replaceChildren(h('div', { class: 'filters' }, [
    filterChip('همه', 'all'), filterChip('ثبت‌شده', 'registered'), filterChip('مهمان', 'guest'),
  ]));
  renderLeftHead();

  const leftPanel = h('div', { class: 'side left' }, [
    h('div', { class: 'side-head' }, [
      h('h3', { text: 'خودروهای پارک‌شده' }),
      h('button', { class: 'icon-btn', html: icons.refresh, onClick: () => { renderParked(); toast('به‌روزرسانی شد'); } }),
    ]),
    leftHead, leftList,
  ]);

  const rightPanel = h('div', { class: 'side right' }, [
    h('div', { class: 'side-head' }, [
      h('h3', { text: 'منتظر پرداخت' }),
      h('button', { class: 'icon-btn', html: icons.refresh, onClick: () => { renderUnpaid(); toast('به‌روزرسانی شد'); } }),
    ]),
    rightList,
  ]);

  // ── Center: cameras + detection ──────────────────────────
  const detectZone = h('div', { class: 'detect-zone idle' });
  const cameraRow = h('div', { class: 'cams' });

  const renderCameras = () => {
    cameraRow.replaceChildren(
      cameraPanel('ورودی', 'entry', store.cameras.entry, () => { store.cameras.entry = !store.cameras.entry; renderCameras(); }),
      cameraPanel('خروجی', 'exit', store.cameras.exit, () => { store.cameras.exit = !store.cameras.exit; renderCameras(); }),
    );
  };
  renderCameras();

  const showIdle = () => {
    detectZone.className = 'detect-zone idle';
    detectZone.replaceChildren(h('div', { class: 'idle-panel' }, [
      h('div', { class: 'radar', html: icons.radar }),
      h('div', { class: 't-headline-sm', style: { color: 'var(--text-muted)' }, text: 'در انتظار تشخیص پلاک' }),
      h('div', { class: 't-body-md', style: { color: 'var(--text-muted)' }, text: 'سیستم آماده دریافت رویداد است' }),
    ]));
  };
  showIdle();

  const renderAll = () => { renderStats(); renderParked(); renderUnpaid(); };
  renderAll();

  // ── Detection simulation loop ────────────────────────────
  let sampleIdx = 0;
  const scheduleDetection = () => {
    detectTimer = setTimeout(() => {
      const sample = store.sampleDetections[sampleIdx % store.sampleDetections.length];
      sampleIdx++;
      const isEntry = sampleIdx % 2 === 1;
      startDetection(sample, isEntry, detectZone, showIdle, renderAll, scheduleDetection);
    }, 6000);
  };
  scheduleDetection();

  root.append(toolbar, statsBar, h('div', { class: 'board' }, [
    leftPanel,
    h('div', { class: 'center' }, [cameraRow, detectZone]),
    rightPanel,
  ]));

  return root;
}

// ── Camera panel ───────────────────────────────────────────
function cameraPanel(name, kind, on, toggle) {
  const cam = h('div', { class: `cam ${kind}` + (on ? ' on' : '') });
  if (on) {
    cam.append(
      h('div', { class: 'cam-noise' }),
      ...['tl', 'tr', 'bl', 'br'].map((p) => h('div', { class: `cam-bracket ${p}` })),
      h('div', { class: 'cam-live' }, [h('span', { class: 'dot' }), 'LIVE']),
      h('div', { class: 'cam-tag', text: `دوربین ${name}` }),
    );
  } else {
    cam.append(h('div', { class: 'cam-off' }, [
      h('div', { html: icons.videocam }),
      h('div', { class: 't-title-md', text: `دوربین ${name}` }),
      h('div', { class: 't-body-sm', style: { color: 'var(--text-muted)' }, text: 'خاموش' }),
    ]));
  }
  cam.append(h('button', { class: 'cam-toggle', html: on ? icons.videocam : icons.videocamOff, onClick: toggle }));
  return cam;
}

// ── Session card (parked + unpaid) ─────────────────────────
function sessionCard(s, isUnpaid, refresh) {
  const cls = s.registered ? 'reg' : 'guest';
  const badgeColor = s.registered ? 'var(--green)' : 'var(--orange)';
  return h('div', { class: `sess ${cls}` }, [
    h('div', { class: 'sess-top' }, [
      plateEl(s.plate, { compact: true }),
      h('span', { class: 'badge', style: { background: 'color-mix(in srgb, ' + badgeColor + ' 15%, transparent)', border: '1px solid ' + badgeColor, color: badgeColor },
        text: s.registered ? 'ثبت' : 'مهمان' }),
    ]),
    h('div', { class: 'sess-user', text: s.user }),
    s.wallet != null && h('div', { class: 'sess-money', text: `💰 ${faMoney(s.wallet)} تومان` }),
    isUnpaid && s.fee != null && h('div', { class: 'sess-debt', text: `بدهی: ${faMoney(s.fee)} تومان` }),
    h('div', { class: 'sess-actions' }, isUnpaid
      ? [
          h('button', { class: 'btn btn-outline btn-sm btn-block', text: 'نقدی', onClick: () => { settleUnpaid(s.id); toast('پرداخت ثبت شد', 'green'); refresh(); } }),
          h('button', { class: 'btn btn-outline btn-sm btn-block', text: 'بخشش', onClick: () => { settleUnpaid(s.id); toast('بدهی بخشیده شد', 'orange'); refresh(); } }),
        ]
      : [
          h('button', { class: 'btn btn-outline btn-sm btn-block', text: 'ثبت خروج', onClick: () => { exitVehicle(s); toast(`خروج ${s.plate} ثبت شد`, 'green'); refresh(); } }),
        ]),
  ]);
}

function settleUnpaid(id) { store.unpaid = store.unpaid.filter((u) => u.id !== id); }
function exitVehicle(s) {
  store.parked = store.parked.filter((p) => p.id !== s.id);
  store.archive.unshift({ id: 9000 + Math.floor(Math.random() * 999), plate: s.plate, dir: 'exit',
    time: new Date().toTimeString().slice(0, 8), operator: store.activeOperator?.name || '—', status: 'paid', fee: 10000 });
}

// ── Detection approval panel ───────────────────────────────
function startDetection(sample, isEntry, zone, showIdle, refresh, reschedule) {
  let max = isEntry ? 15 : (sample.registered ? (sample.wallet > 0 ? 5 : 10) : 45);
  let count = max;
  const fee = isEntry ? null : 50000;

  const ring = h('div', { class: 'ring' });
  const renderRing = () => {
    const R = 24, C = 2 * Math.PI * R;
    const warn = count <= 5;
    ring.className = 'ring' + (warn ? ' warn' : '');
    ring.innerHTML = `<svg width="56" height="56">
      <circle class="track" cx="28" cy="28" r="${R}"/>
      <circle class="prog" cx="28" cy="28" r="${R}" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - count / max)}"/>
    </svg><div class="num">${faNum(count)}</div>`;
  };
  renderRing();

  const finish = (approved, msg, kind) => {
    clearInterval(countdownTimer); countdownTimer = null;
    if (approved) applyDetection(sample, isEntry);
    toast(msg, kind);
    refresh();
    showIdle();
    reschedule();
  };

  const metaRow = (k, v, color) => h('div', { class: 'meta-row' }, [
    h('span', { class: 'k', text: k }), h('span', { class: 'v', style: color ? { color } : {}, text: v }),
  ]);

  const statusText = sample.registered ? 'ثبت‌شده' : 'مهمان';
  const statusColor = sample.registered ? 'var(--green)' : 'var(--orange)';

  const metaRows = [
    metaRow('وضعیت', statusText, statusColor),
    metaRow('نام', sample.owner),
    sample.phone && metaRow('موبایل', sample.phone),
    metaRow('کیف پول', sample.wallet != null ? `${faMoney(sample.wallet)} ت` : '—', sample.wallet > 0 ? 'var(--green)' : null),
    !isEntry && fee != null && metaRow('هزینه', `${faMoney(fee)} ت`, 'var(--orange)'),
    metaRow('اطمینان', `${faNum(Math.round(sample.confidence * 100))}٪`, 'var(--green)'),
  ];

  const guestExit = !isEntry && !sample.registered;

  const actions = [
    h('button', { class: 'btn btn-outline-red btn-block', text: 'رد', onClick: () => finish(false, 'تشخیص رد شد', 'red') }),
    guestExit && h('button', { class: 'btn btn-green btn-block', text: 'دریافت شد',
      onClick: () => finish(true, `خروج مهمان — هزینه: ${faMoney(fee)} تومان`, 'green') }),
    h('button', {
      class: 'btn btn-block ' + (isEntry ? 'btn-green' : 'btn-orange'),
      text: isEntry ? 'تایید ورود' : 'تایید خروج',
      onClick: () => finish(true, `${isEntry ? 'ورود' : 'خروج'} ${sample.plate} ثبت شد`, isEntry ? 'green' : 'orange'),
    }),
  ];

  zone.className = 'detect-zone';
  zone.replaceChildren(h('div', { class: 'detect' }, [
    h('div', { class: 'detect-head' }, [
      h('span', { class: 'dot' }),
      h('span', { class: 'title', text: 'پلاک شناسایی شد' }),
      h('span', { class: 'badge', style: { background: 'rgba(59,130,246,.12)', border: '1px solid var(--blue)', color: 'var(--blue)' },
        text: isEntry ? 'ورودی' : 'خروجی' }),
      h('div', { class: 'spacer' }),
      ring,
    ]),
    h('div', { class: 'detect-body' }, [
      h('div', { class: 'detect-meta' }, [
        h('div', { class: 'plate-center' }, [plateEl(sample.plate)]),
        h('div', { class: 'meta-box' }, metaRows.filter(Boolean)),
        guestExit && h('div', { class: 'alert err' }, [h('span', { html: icons.info }), 'پلاک ثبت نشده']),
      ].filter(Boolean)),
      h('div', { class: 'detect-actions' }, actions.filter(Boolean)),
    ]),
  ]));

  if (max > 0) {
    countdownTimer = setInterval(() => {
      count--;
      renderRing();
      if (count <= 0) {
        finish(true, `${isEntry ? 'ورود' : 'خروج'} ${sample.plate} (تایید خودکار)`, 'green');
      }
    }, 1000);
  }
}

function applyDetection(sample, isEntry) {
  if (isEntry) {
    if (!store.parked.some((p) => p.plate === sample.plate)) {
      store.parked.unshift({ id: Date.now(), plate: sample.plate, user: sample.owner === '—' ? 'مهمان' : sample.owner,
        registered: sample.registered, wallet: sample.wallet, freeZone: null });
    }
    store.archive.unshift({ id: 9000 + Math.floor(Math.random() * 999), plate: sample.plate, dir: 'entry',
      time: new Date().toTimeString().slice(0, 8), operator: store.activeOperator?.name || '—',
      status: sample.registered ? 'paid' : 'unpaid', fee: 0 });
  } else {
    store.parked = store.parked.filter((p) => p.plate !== sample.plate);
    store.archive.unshift({ id: 9000 + Math.floor(Math.random() * 999), plate: sample.plate, dir: 'exit',
      time: new Date().toTimeString().slice(0, 8), operator: store.activeOperator?.name || '—', status: 'paid', fee: 50000 });
  }
}
