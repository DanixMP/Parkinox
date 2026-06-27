import { store } from './store.js';
import { renderLogin } from './views/login.js';
import { renderDashboard, disposeDashboard } from './views/dashboard.js';
import { renderSettings } from './views/settings.js';
import { renderArchive } from './views/archive.js';

const root = document.getElementById('root');
let current = 'login';

const routes = {
  login: renderLogin,
  dashboard: renderDashboard,
  settings: renderSettings,
  archive: renderArchive,
};

function navigate(route) {
  // Guard: dashboard/archive require an active operator.
  if ((route === 'dashboard' || route === 'archive') && !store.activeOperator) route = 'login';
  if (current === 'dashboard' && route !== 'dashboard') disposeDashboard();
  current = route;
  root.replaceChildren(routes[route](navigate));
}

navigate('login');
