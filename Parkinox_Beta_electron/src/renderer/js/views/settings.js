import { h, faMoney, toast } from '../util.js';
import { icons } from '../icons.js';
import { store } from '../store.js';

export function renderSettings(navigate) {
  const back = store.activeOperator ? 'dashboard' : 'login';

  const toggleRow = (name, desc, getter, setter) => {
    const sw = h('div', { class: 'switch' + (getter() ? ' on' : '') });
    sw.addEventListener('click', () => { setter(!getter()); sw.classList.toggle('on', getter()); toast('ذخیره شد'); });
    return h('div', { class: 'setting-row' }, [
      h('div', { class: 'info' }, [h('div', { class: 'name', text: name }), h('div', { class: 'desc', text: desc })]),
      sw,
    ]);
  };

  const numberRow = (name, desc, value, onChange, suffix = '') => {
    const input = h('input', { type: 'number', value, style: { width: '120px', textAlign: 'center' } });
    input.addEventListener('change', () => { onChange(+input.value); toast('ذخیره شد'); });
    return h('div', { class: 'setting-row' }, [
      h('div', { class: 'info' }, [h('div', { class: 'name', text: name }), h('div', { class: 'desc', text: desc })]),
      h('div', { style: { display: 'flex', alignItems: 'center', gap: '8px' } }, [input, suffix && h('span', { class: 'desc', text: suffix })]),
    ]);
  };

  return h('div', { class: 'page' }, [
    h('div', { class: 'page-head' }, [
      h('button', { class: 'icon-btn', html: icons.back, onClick: () => navigate(back) }),
      h('h1', { text: 'تنظیمات' }),
    ]),

    h('div', { class: 'card' }, [
      h('h3', { text: 'سرور و اتصال' }),
      fieldRow('آدرس Django', 'http://localhost:8000'),
      fieldRow('آدرس FastAPI', 'http://localhost:9000'),
      fieldRow('موبایل سوپریوزر', '۰۹۱۲۰۰۰۰۰۰۰'),
    ]),

    h('div', { class: 'card' }, [
      h('h3', { text: 'دوربین‌ها' }),
      toggleRow('دوربین ورودی', 'فعال‌سازی تشخیص پلاک ورودی', () => store.cameras.entry, (v) => store.cameras.entry = v),
      toggleRow('دوربین خروجی', 'فعال‌سازی تشخیص پلاک خروجی', () => store.cameras.exit, (v) => store.cameras.exit = v),
      fieldRow('نوع دوربین ورودی', 'دوربین محلی', 'select', ['دوربین محلی', 'دوربین IP']),
      fieldRow('نوع دوربین خروجی', 'دوربین محلی', 'select', ['دوربین محلی', 'دوربین IP']),
    ]),

    h('div', { class: 'card' }, [
      h('h3', { text: 'نرخ‌گذاری' }),
      numberRow('نرخ ساعتی', 'تومان به ازای هر ساعت', store.rates.ratePerHour, (v) => store.rates.ratePerHour = v, 'تومان'),
      numberRow('مهلت رایگان', 'دقیقه', store.rates.gracePeriodMinutes, (v) => store.rates.gracePeriodMinutes = v, 'دقیقه'),
      numberRow('سقف روزانه', 'تومان', store.rates.dailyCap, (v) => store.rates.dailyCap = v, 'تومان'),
    ]),

    h('div', { class: 'card' }, [
      h('h3', { text: 'تشخیص خودکار' }),
      numberRow('مهلت شمارش معکوس ورود', 'ثانیه تا تایید خودکار', 15, () => {}, 'ثانیه'),
    ]),
  ]);
}

function fieldRow(label, value, type = 'text', options = []) {
  if (type === 'select') {
    return h('div', { class: 'field' }, [
      h('label', { text: label }),
      h('select', {}, options.map((o) => h('option', { text: o, selected: o === value }))),
    ]);
  }
  return h('div', { class: 'field' }, [h('label', { text: label }), h('input', { type, value })]);
}
