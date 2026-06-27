// In-memory mock store mirroring the Django/parking models the Flutter app reads.
// Lets the Beta UI run fully standalone (no backend) while keeping the same shapes.

export const store = {
  activeOperator: null,

  operators: [
    { id: 'op1', name: 'علی رضایی', role: 'سرپرست شیفت', color: '#3b82f6' },
    { id: 'op2', name: 'مریم حسینی', role: 'اپراتور', color: '#22c55e' },
    { id: 'op3', name: 'رضا کریمی', role: 'اپراتور', color: '#f97316' },
  ],

  health: { fastApi: true, django: true, ws: true },

  rates: { ratePerHour: 5000, gracePeriodMinutes: 15, dailyCap: 50000 },

  cameras: { entry: true, exit: true },

  // Parked vehicles (ParkingSessionSummary)
  parked: [
    { id: 1, plate: '12 ب 345 17', user: 'علی رضایی', registered: true, wallet: 120000, freeZone: null },
    { id: 2, plate: '88 ج 217 22', user: 'مهمان', registered: false, wallet: null, freeZone: null },
    { id: 3, plate: '45 د 678 11', user: 'سارا احمدی', registered: true, wallet: 35000, freeZone: null },
    { id: 4, plate: '33 س 901 99', user: 'مهمان', registered: false, wallet: null, freeZone: null },
    { id: 5, plate: '77 ط 432 10', user: 'حسین مرادی', registered: true, wallet: 8000, freeZone: null },
  ],

  // Unpaid sessions
  unpaid: [
    { id: 101, plate: '88 ج 217 22', user: 'مهمان', registered: false, wallet: null, fee: 25000, freeZone: null },
    { id: 102, plate: '77 ط 432 10', user: 'حسین مرادی', registered: true, wallet: 8000, fee: 15000, freeZone: null },
  ],

  // Archive (recent gate events)
  archive: [
    { id: 9001, plate: '12 ب 345 17', dir: 'entry', time: '08:12:04', operator: 'علی رضایی', status: 'paid', fee: 0 },
    { id: 9002, plate: '88 ج 217 22', dir: 'entry', time: '08:31:55', operator: 'علی رضایی', status: 'unpaid', fee: 0 },
    { id: 9003, plate: '45 د 678 11', dir: 'entry', time: '09:02:17', operator: 'مریم حسینی', status: 'paid', fee: 0 },
    { id: 9004, plate: '21 ل 555 44', dir: 'exit', time: '09:45:30', operator: 'مریم حسینی', status: 'paid', fee: 10000 },
    { id: 9005, plate: '33 س 901 99', dir: 'entry', time: '10:10:01', operator: 'رضا کریمی', status: 'unpaid', fee: 0 },
  ],

  // Sample plates the "detector" cycles through
  sampleDetections: [
    { plate: '12 ب 345 17', confidence: 0.97, registered: true, owner: 'علی رضایی', phone: '۰۹۱۲۳۴۵۶۷۸۹', wallet: 120000 },
    { plate: '99 ق 111 25', confidence: 0.91, registered: false, owner: '—', phone: null, wallet: null },
    { plate: '45 د 678 11', confidence: 0.88, registered: true, owner: 'سارا احمدی', phone: '۰۹۳۵۱۱۱۲۲۳۳', wallet: 35000 },
  ],
};

// Simple pub/sub so views re-render on state change.
const subs = new Set();
export function subscribe(fn) { subs.add(fn); return () => subs.delete(fn); }
export function emit() { subs.forEach((fn) => fn()); }
