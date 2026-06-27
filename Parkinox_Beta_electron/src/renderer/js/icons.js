// Inline SVG icon set (Material-style, matching the Flutter icons used).
const I = (p) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;

export const icons = {
  parking: I('<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 17V7h4a3 3 0 0 1 0 6H9"/>'),
  calendar: I('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>'),
  clock: I('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  tools: I('<circle cx="12" cy="12" r="9"/><path d="M12 8v4l2 2"/><path d="M9 3h6"/>'),
  archive: I('<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>'),
  wallet: I('<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M16 12h2M3 9h18"/>'),
  settings: I('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a7.97 7.97 0 0 0 0-6l1.5-1.2-2-3.5-1.8.7a8 8 0 0 0-2.6-1.5L14 0h-4l-.5 2.5A8 8 0 0 0 6.9 4l-1.8-.7-2 3.5L4.6 9a7.97 7.97 0 0 0 0 6l-1.5 1.2 2 3.5 1.8-.7a8 8 0 0 0 2.6 1.5L10 24h4l.5-2.5a8 8 0 0 0 2.6-1.5l1.8.7 2-3.5z"/>'),
  logout: I('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>'),
  refresh: I('<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>'),
  videocam: I('<rect x="2" y="6" width="14" height="12" rx="2"/><path d="M22 8l-6 4 6 4z"/>'),
  videocamOff: I('<path d="M2 2l20 20"/><rect x="2" y="6" width="14" height="12" rx="2"/><path d="M22 8l-6 4 6 4z"/>'),
  radar: I('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/><path d="M12 12l6-4"/>'),
  chevron: I('<path d="M15 6l-6 6 6 6"/>'),
  add: I('<path d="M12 5v14M5 12h14"/>'),
  check: I('<path d="M20 6L9 17l-5-5"/>'),
  close: I('<path d="M18 6L6 18M6 6l12 12"/>'),
  warning: I('<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'),
  info: I('<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>'),
  user: I('<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'),
  cash: I('<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>'),
  back: I('<path d="M5 12h14M5 12l6-6M5 12l6 6"/>'),
};
