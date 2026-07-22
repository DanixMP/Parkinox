# Remote Management Cloud (Pilot E2E)

Local SoR = `backend/` + `Core/`. Cloud replica = `cloud/`.

## Offline / outage checklist

1. Set `CLOUD_SYNC_ENABLED=false` or disconnect network.
2. Confirm several entry/exit events via operator app.
3. Local reporting and gate flow must succeed.
4. `GET /api/parking/sync/status/` shows pending outbox rows (when sync enabled and events enqueued).
5. Restore network / set `CLOUD_SYNC_ENABLED=true`.
6. Run `python manage.py sync_to_cloud --once` from `backend/`.
7. Open cloud dashboard — session counts match local; no duplicate UUIDs after second sync.
8. Images may arrive later; session detail shows pending until upload completes.

## Related docs

- [cloud/README.md](../cloud/README.md)
- [cloud/DEPLOYMENT.md](../cloud/DEPLOYMENT.md)
- [DETECTION_FAIL_CAPTURE.md](DETECTION_FAIL_CAPTURE.md) (pattern mirrored by success capture)
