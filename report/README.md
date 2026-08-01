# Parkinox Reports

Blue-themed success and data analytics documents generated from operational session export.

## Outputs

| File | Description |
|------|-------------|
| `Parkinox_Success_Report.docx` | System success narrative, architecture, error handling, Iranian plate ledger (all sessions), and charts |
| `Parkinox_Data_Analytics_Report.docx` | CSV-only analytics: measured date/time charts, daily/hourly tables, duration & fee stats |
| `charts/` | PNG charts shared by both documents |
| `plates/` | Cached Iranian-style plate badge PNGs |
| `parkinox_sessions.csv` | Source session export |

## Regenerate

```bash
pip install python-docx matplotlib pillow pandas
python report/generate_reports.py
```
