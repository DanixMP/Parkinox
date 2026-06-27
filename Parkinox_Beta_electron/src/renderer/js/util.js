// === Persian helpers (mirrors core/utils/persian_utils.dart) ===
const FA_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

export function faNum(input) {
  return String(input).replace(/\d/g, (d) => FA_DIGITS[+d]);
}

export function faMoney(n) {
  if (n == null) return '—';
  return faNum(Math.round(n).toLocaleString('en-US'));
}

export const WEEKDAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه'];

// Tiny Gregorian→Jalali conversion (for the toolbar clock).
export function toJalali(gy, gm, gd) {
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  let jy = gy <= 1600 ? 0 : 979;
  gy -= gy <= 1600 ? 621 : 1600;
  const gy2 = gm > 2 ? gy + 1 : gy;
  let days =
    365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
  jy += 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) { jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return [jy, jm, jd];
}

// === DOM mini-helper ===
export function h(tag, attrs = {}, children = []) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else el.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(c));
  }
  return el;
}

// === Iranian plate renderer (mirrors dashboard_screen _buildIranianPlate) ===
// plate string format: "12 ب 345 17" -> series letter serial region
export function plateEl(plateStr, { compact = false } = {}) {
  const parts = String(plateStr).trim().split(/\s+/);
  if (parts.length < 4) {
    return h('div', { class: 'plate' + (compact ? ' compact' : '') }, [
      h('div', { class: 'plate-nums', text: faNum(plateStr) }),
    ]);
  }
  const [series, letter, serial, region] = parts;
  return h('div', { class: 'plate' + (compact ? ' compact' : '') }, [
    h('div', { class: 'plate-blue' }, [
      h('div', { class: 'plate-flag' }, [
        h('span', { class: 'g' }), h('span', { class: 'w' }), h('span', { class: 'r' }),
      ]),
      h('small', { text: 'I.R.' }),
      h('small', { text: 'IRAN' }),
    ]),
    h('div', { class: 'plate-nums' }, [
      h('div', { class: 'plate-region' }, [
        h('span', { class: 'ir', text: 'ایران' }),
        h('span', { class: 'rn', text: faNum(region) }),
      ]),
      h('div', { class: 'plate-vsep' }),
      h('span', { class: 'plate-serial', text: faNum(serial) }),
      h('span', { class: 'plate-letter', text: letter }),
      h('span', { class: 'plate-series', text: faNum(series) }),
    ]),
  ]);
}

// === Toast ===
let toastHost;
export function toast(message, kind = 'green', ms = 3000) {
  if (!toastHost) {
    toastHost = h('div', { class: 'toast-host' });
    document.body.append(toastHost);
  }
  const t = h('div', { class: `toast ${kind}`, text: message });
  toastHost.append(t);
  setTimeout(() => {
    t.style.transition = 'opacity .25s, transform .25s';
    t.style.opacity = '0';
    t.style.transform = 'translateY(8px)';
    setTimeout(() => t.remove(), 250);
  }, ms);
}
