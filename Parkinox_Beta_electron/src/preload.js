const { contextBridge } = require('electron');

// Minimal, safe bridge. The Beta UI runs on mock data and needs no privileged
// APIs yet — this keeps a single seam for wiring the real backend later.
contextBridge.exposeInMainWorld('parkinox', {
  version: '0.1.0',
  platform: process.platform,
});
