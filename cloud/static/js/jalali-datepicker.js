/**
 * Lightweight Jalali calendar for .jalali-date-input fields.
 * Writes yyyy/MM/dd with Persian digits (compatible with dashboard.jalali.parse_jalali_date).
 */
(function () {
  const FA = '۰۱۲۳۴۵۶۷۸۹';
  const MONTHS = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  const WEEKDAYS = ['ش','ی','د','س','چ','پ','ج'];

  function toFa(n) {
    return String(n).replace(/\d/g, (d) => FA[+d]);
  }
  function toEn(s) {
    return String(s)
      .replace(/[۰-۹]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
      .replace(/[٠-٩]/g, (d) => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
  }

  // Algorithm from jalaali-js (public domain style conversion)
  function div(a, b) { return ~~(a / b); }
  function g2j(gy, gm, gd) {
    const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    let gy2 = gm > 2 ? gy + 1 : gy;
    let days = 355666 + (365 * gy) + div(gy2 + 3, 4) - div(gy2 + 99, 100) + div(gy2 + 399, 400) + gd + g_d_m[gm - 1];
    let jy = -1595 + (33 * div(days, 12053));
    days %= 12053;
    jy += 4 * div(days, 1461);
    days %= 1461;
    if (days > 365) {
      jy += div(days - 1, 365);
      days = (days - 1) % 365;
    }
    let jm, jd;
    if (days < 186) {
      jm = 1 + div(days, 31);
      jd = 1 + (days % 31);
    } else {
      jm = 7 + div(days - 186, 30);
      jd = 1 + ((days - 186) % 30);
    }
    return { jy, jm, jd };
  }
  function j2g(jy, jm, jd) {
    jy += 1595;
    let days = -355668 + (365 * jy) + (div(jy, 33) * 8) + div((jy % 33) + 3, 4) + jd
      + (jm < 7 ? (jm - 1) * 31 : ((jm - 7) * 30) + 186);
    let gy = 400 * div(days, 146097);
    days %= 146097;
    if (days > 36524) {
      gy += 100 * div(--days, 36524);
      days %= 36524;
      if (days >= 365) days++;
    }
    gy += 4 * div(days, 1461);
    days %= 1461;
    if (days > 365) {
      gy += div(days - 1, 365);
      days = (days - 1) % 365;
    }
    let gd = days + 1;
    const sal_a = [0, 31, ((gy % 4 === 0 && gy % 100 !== 0) || (gy % 400 === 0)) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let gm = 0;
    for (gm = 1; gm <= 12 && gd > sal_a[gm]; gm++) gd -= sal_a[gm];
    return { gy, gm, gd };
  }
  function jMonthLength(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    // Esfand: leap if remainder of (jy-979) cycle
    const a = jy - 979;
    const leap = (((a % 33) + 33) % 33) % 4 === 1;
    // More accurate: use conversion of last day
    const g = j2g(jy, 12, 30);
    const j = g2j(g.gy, g.gm, g.gd);
    return j.jm === 12 && j.jd === 30 ? 30 : 29;
  }
  // Better month length: try day 30 then 29
  function daysInMonth(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    const g30 = j2g(jy, 12, 30);
    const back = g2j(g30.gy, g30.gm, g30.gd);
    return (back.jy === jy && back.jm === 12 && back.jd === 30) ? 30 : 29;
  }
  function formatJalali(jy, jm, jd) {
    return toFa(
      String(jy).padStart(4, '0') + '/' +
      String(jm).padStart(2, '0') + '/' +
      String(jd).padStart(2, '0')
    );
  }
  function parseInput(val) {
    const raw = toEn((val || '').trim()).replace(/-/g, '/');
    const p = raw.split('/').filter(Boolean);
    if (p.length !== 3) return null;
    const jy = +p[0], jm = +p[1], jd = +p[2];
    if (!jy || !jm || !jd) return null;
    return { jy, jm, jd };
  }
  function todayJ() {
    const n = new Date();
    return g2j(n.getFullYear(), n.getMonth() + 1, n.getDate());
  }
  function weekdayOf(jy, jm, jd) {
    const g = j2g(jy, jm, jd);
    const d = new Date(g.gy, g.gm - 1, g.gd);
    // JS: 0=Sun … convert to Iranian week starting Saturday
    return (d.getDay() + 1) % 7;
  }

  let openPopup = null;

  function closeAll() {
    document.querySelectorAll('.jdp-popup.open').forEach((el) => el.classList.remove('open'));
    openPopup = null;
  }

  function buildPopup(input) {
    const wrap = document.createElement('div');
    wrap.className = 'jdp-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    const popup = document.createElement('div');
    popup.className = 'jdp-popup';
    popup.innerHTML = [
      '<div class="jdp-header">',
      '<button type="button" data-jdp="prev" aria-label="ماه قبل">‹</button>',
      '<div class="jdp-title"></div>',
      '<button type="button" data-jdp="next" aria-label="ماه بعد">›</button>',
      '</div>',
      '<div class="jdp-weekdays">' + WEEKDAYS.map((w) => '<span>' + w + '</span>').join('') + '</div>',
      '<div class="jdp-days"></div>',
      '<div class="jdp-footer">',
      '<button type="button" data-jdp="clear">پاک کردن</button>',
      '<button type="button" class="primary" data-jdp="today">امروز</button>',
      '</div>',
    ].join('');
    wrap.appendChild(popup);

    let view = parseInput(input.value) || todayJ();
    view = { jy: view.jy, jm: view.jm, jd: view.jd || 1 };

    function render() {
      popup.querySelector('.jdp-title').textContent = MONTHS[view.jm - 1] + ' ' + toFa(view.jy);
      const daysEl = popup.querySelector('.jdp-days');
      daysEl.innerHTML = '';
      const dim = daysInMonth(view.jy, view.jm);
      const start = weekdayOf(view.jy, view.jm, 1);
      const selected = parseInput(input.value);
      const today = todayJ();
      for (let i = 0; i < start; i++) {
        const b = document.createElement('button');
        b.type = 'button';
        b.disabled = true;
        daysEl.appendChild(b);
      }
      for (let d = 1; d <= dim; d++) {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = toFa(d);
        if (selected && selected.jy === view.jy && selected.jm === view.jm && selected.jd === d) {
          b.classList.add('selected');
        }
        if (today.jy === view.jy && today.jm === view.jm && today.jd === d) {
          b.classList.add('today');
        }
        b.addEventListener('click', () => {
          input.value = formatJalali(view.jy, view.jm, d);
          input.dispatchEvent(new Event('change', { bubbles: true }));
          closeAll();
        });
        daysEl.appendChild(b);
      }
    }

    popup.querySelector('[data-jdp="prev"]').addEventListener('click', (e) => {
      e.stopPropagation();
      view.jm -= 1;
      if (view.jm < 1) { view.jm = 12; view.jy -= 1; }
      render();
    });
    popup.querySelector('[data-jdp="next"]').addEventListener('click', (e) => {
      e.stopPropagation();
      view.jm += 1;
      if (view.jm > 12) { view.jm = 1; view.jy += 1; }
      render();
    });
    popup.querySelector('[data-jdp="today"]').addEventListener('click', (e) => {
      e.stopPropagation();
      const t = todayJ();
      input.value = formatJalali(t.jy, t.jm, t.jd);
      input.dispatchEvent(new Event('change', { bubbles: true }));
      closeAll();
    });
    popup.querySelector('[data-jdp="clear"]').addEventListener('click', (e) => {
      e.stopPropagation();
      input.value = '';
      input.dispatchEvent(new Event('change', { bubbles: true }));
      closeAll();
    });

    input.addEventListener('click', (e) => {
      e.stopPropagation();
      if (openPopup === popup) { closeAll(); return; }
      closeAll();
      const cur = parseInput(input.value);
      if (cur) view = { jy: cur.jy, jm: cur.jm, jd: cur.jd };
      else {
        const t = todayJ();
        view = { jy: t.jy, jm: t.jm, jd: t.jd };
      }
      render();
      popup.classList.add('open');
      openPopup = popup;
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeAll();
    });
    popup.addEventListener('click', (e) => e.stopPropagation());
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input.jalali-date-input').forEach(buildPopup);
  });
  document.addEventListener('click', closeAll);
})();
