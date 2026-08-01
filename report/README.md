# Parkinox Reports

Blue-themed success and data analytics documents (English + Persian) generated from the operational session export.

## Outputs

| File | Description |
|------|-------------|
| `Parkinox_Success_Report.docx` | English success narrative, architecture, error handling, Iranian plate ledger, charts |
| `Parkinox_Success_Report_FA.docx` | **Persian RTL** edition of the success report |
| `Parkinox_Data_Analytics_Report.docx` | English CSV-only analytics |
| `Parkinox_Data_Analytics_Report_FA.docx` | **Persian RTL** edition of the data analytics report |
| `charts/` | PNG charts (English + `fa_*` Persian-labeled) |
| `plates/` | Cached Iranian-style plate badge PNGs |
| `parkinox_sessions.csv` | Source session export |
| `generate_reports.py` / `persian_reports.py` | Generators |

## Regenerate

```bash
pip install python-docx matplotlib pillow pandas
python report/generate_reports.py
```
