(function () {
  const LETTERS = ['الف','ب','پ','ت','ث','ج','چ','ح','خ','د','ذ','ر','ز','ژ','س','ش','ص','ض','ط','ظ','ع','غ','ف','ق','ک','گ','ل','م','ن','و','ه','ی'];
  const DIGIT_FA = '۰۱۲۳۴۵۶۷۸۹';
  const DIGIT_EN = '0123456789';

  function toFa(ch) {
    const i = DIGIT_EN.indexOf(ch);
    return i >= 0 ? DIGIT_FA[i] : ch;
  }
  function toEn(ch) {
    const i = DIGIT_FA.indexOf(ch);
    if (i >= 0) return DIGIT_EN[i];
    const ar = '٠١٢٣٤٥٦٧٨٩';
    const j = ar.indexOf(ch);
    return j >= 0 ? DIGIT_EN[j] : ch;
  }

  function assemble(root) {
    const d = (id) => (root.querySelector('[data-plate="' + id + '"]') || {}).value || '';
    const letterBtn = root.querySelector('[data-plate="letter"]');
    const letter = (letterBtn && letterBtn.dataset.value) || '';
    const p1 = toEn(d('d1')), p2 = toEn(d('d2'));
    const s1 = toEn(d('d3')), s2 = toEn(d('d4')), s3 = toEn(d('d5'));
    const r1 = toEn(d('d6')), r2 = toEn(d('d7'));
    const prefix = (p1 + p2).trim();
    const serial = (s1 + s2 + s3).trim();
    const region = (r1 + r2).trim();
    if (!prefix && !letter && !serial && !region) return '';
    // Canonical-ish for icontains: ۱۲ب۳۴۵-۶۷ and also spaced
    const fa = (s) => s.split('').map(toFa).join('');
    return fa(prefix) + letter + fa(serial) + (region ? '-' + fa(region) : '');
  }

  function syncHidden(root) {
    const hidden = root.querySelector('input[type="hidden"][name="plate"]');
    if (hidden) hidden.value = assemble(root);
  }

  function openLetterPicker(root, btn) {
    let overlay = document.getElementById('plate-letter-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'plate-letter-overlay';
      overlay.className = 'letter-picker-overlay';
      overlay.innerHTML = '<div class="letter-picker-sheet"><h3>انتخاب حرف پلاک</h3><div class="letter-grid"></div></div>';
      document.body.appendChild(overlay);
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.remove('show');
      });
    }
    const grid = overlay.querySelector('.letter-grid');
    grid.innerHTML = '';
    LETTERS.forEach((L) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = L;
      b.addEventListener('click', () => {
        btn.dataset.value = L;
        btn.textContent = L;
        btn.classList.remove('empty');
        syncHidden(root);
        overlay.classList.remove('show');
      });
      grid.appendChild(b);
    });
    overlay.classList.add('show');
  }

  function wireRoot(root) {
    if (!root || root.dataset.wired) return;
    root.dataset.wired = '1';
    root.querySelectorAll('.plate-digit').forEach((input) => {
      input.addEventListener('input', () => {
        let v = toEn((input.value || '').slice(-1));
        if (!/^\d$/.test(v)) v = '';
        input.value = v ? toFa(v) : '';
        if (v) input.classList.add('filled'); else input.classList.remove('filled');
        syncHidden(root);
        if (v) {
          const cells = Array.from(root.querySelectorAll('.plate-digit, .plate-letter'));
          const idx = cells.indexOf(input);
          if (idx >= 0 && idx < cells.length - 1) {
            const next = cells[idx + 1];
            if (next && next.tagName === 'INPUT') next.focus();
            else if (next) next.focus();
          }
        }
      });
    });
    const letterBtn = root.querySelector('[data-plate="letter"]');
    if (letterBtn) {
      letterBtn.addEventListener('click', () => openLetterPicker(root, letterBtn));
    }
    const form = root.closest('form');
    if (form) {
      form.addEventListener('submit', () => syncHidden(root));
    }
    // Prefill from hidden
    const hidden = root.querySelector('input[type="hidden"][name="plate"]');
    if (hidden && hidden.value) {
      // leave visual empty; search still works via hidden
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.plate-input-ir').forEach(wireRoot);
  });
})();
