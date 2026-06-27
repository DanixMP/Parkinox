import { h, toast } from '../util.js';
import { icons } from '../icons.js';
import { store, emit } from '../store.js';

const PIN = '123456'; // demo superuser PIN

export function renderLogin(navigate) {
  return h('div', { class: 'login-wrap' }, [
    h('div', { class: 'login-card' }, [
      h('div', { class: 'login-logo', html: icons.parking }),
      h('h1', { class: 'login-title t-display-md', text: 'ورود اپراتور' }),
      h('p', { class: 'login-sub', text: 'پروفایل خود را انتخاب کنید' }),
      h('div', { class: 'login-ops' },
        store.operators.map((op) =>
          h('button', { class: 'op-card', onClick: () => openPin(op, navigate) }, [
            h('div', { class: 'op-avatar', style: { background: op.color }, text: op.name[0] }),
            h('div', { class: 'op-info' }, [
              h('div', { class: 'op-name', text: op.name }),
              h('div', { class: 'op-role', text: op.role }),
            ]),
            h('div', { class: 'op-chev', html: icons.chevron }),
          ]),
        ),
      ),
      h('div', { class: 'login-actions' }, [
        h('button', { class: 'btn btn-ghost', onClick: () => navigate('settings'),
          html: icons.settings + '<span>تنظیمات راه‌اندازی</span>' }),
        h('button', { class: 'btn btn-ghost', onClick: () => toast('افزودن اپراتور در نسخه دمو غیرفعال است', 'orange'),
          html: icons.add + '<span>افزودن اپراتور</span>' }),
      ]),
    ]),
  ]);
}

function openPin(op, navigate) {
  let entered = '';
  const cells = [];

  const update = () => {
    cells.forEach((c, i) => {
      c.classList.toggle('filled', i < entered.length);
      c.classList.toggle('active', i === entered.length);
      c.textContent = i < entered.length ? '•' : '';
    });
  };

  const submit = () => {
    if (entered === PIN) {
      store.activeOperator = op;
      emit();
      overlay.remove();
      document.removeEventListener('keydown', onKey);
      navigate('dashboard');
      toast(`خوش آمدید، ${op.name}`, 'green');
    } else {
      modal.animate(
        [{ transform: 'translateX(-8px)' }, { transform: 'translateX(8px)' }, { transform: 'translateX(0)' }],
        { duration: 250 },
      );
      entered = '';
      update();
      toast('رمز اشتباه است (دمو: ۱۲۳۴۵۶)', 'red');
    }
  };

  const press = (d) => { if (entered.length < 6) { entered += d; update(); if (entered.length === 6) setTimeout(submit, 120); } };
  const back = () => { entered = entered.slice(0, -1); update(); };

  const onKey = (e) => {
    if (e.key >= '0' && e.key <= '9') press(e.key);
    else if (e.key === 'Backspace') back();
    else if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', onKey); }
  };
  document.addEventListener('keydown', onKey);

  for (let i = 0; i < 6; i++) cells.push(h('div', { class: 'pin-cell' }));

  const keypad = h('div', { class: 'keypad' },
    [...'123456789'].map((d) => h('button', { class: 'key', text: d, onClick: () => press(d) }))
      .concat([
        h('button', { class: 'key', html: icons.close, onClick: back }),
        h('button', { class: 'key', text: '0', onClick: () => press('0') }),
        h('button', { class: 'key', html: icons.check, style: { color: 'var(--green)' }, onClick: submit }),
      ]),
  );

  const modal = h('div', { class: 'modal' }, [
    h('h2', { text: op.name }),
    h('p', { text: 'رمز ۶ رقمی سوپریوزر را وارد کنید' }),
    h('div', { class: 'pin-grid' }, cells),
    keypad,
  ]);
  const overlay = h('div', { class: 'overlay', onClick: (e) => { if (e.target === overlay) { overlay.remove(); document.removeEventListener('keydown', onKey); } } }, [modal]);
  document.body.append(overlay);
  update();
}
