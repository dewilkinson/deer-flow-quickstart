# Cobalt Multi-Agent: Zero-Dependency UX Tests

This directory catalogs all interactive, GUI-based tests and dashboards within the Cobalt Multi-Agent repository. Because of our strict commitment to VLI (Very Low Latency Interface) and minimal bloat, our UX tests are built as "Zero-Dependency" dashboards natively using Python's `webbrowser` built-in. 

These scripts construct localized HTML and launch browser views dynamically without requiring Node.js, React, or complex web-server hosting.

## Catalog of Active UX Dashboards

### 1. The VLI Session Dashboard (DAL offline emulator)
**Location:** `backend/scripts/dashboard_vli.py`

**Description:**
A premium, dark-mode VLI terminal replication used to audit the Data Access Layer (DAL). It strips the SnapTrade credentials, mocks a localized broker connection to your `Accounts_History.csv`, executes the FIFO Reconciliation Engine, and generates 3 distinct agent panes (Portfolio Manager, Risk Manager, Journaler) to visualize exactly what text data the AI is receiving dynamically. 

**Execution:**
```powershell
uv run python backend/scripts/dashboard_vli.py
```

### 2. TradeZella Extractor Audit Dashboard
**Location:** `tools/csv-to-tradezella/csv-to-tradezella.py`

**Description:**
An interactive status dashboard generated automatically when processing Fidelity CSV backups. It provides a visual table mapping the success of the chronological reversing algorithm, highlights "orphaned" trades that required lookback reconciliation, and outputs the theoretical FIFO ROI before it is pushed to TradeZella.

**Execution:**
```powershell
python tools/csv-to-tradezella/csv-to-tradezella.py --reconcile
# Use --ytd, --day, or --range keywords to filter the UI
```

---
*Note: All dashboards construct their mock data securely inside `tempfile` structures which are immediately cleared by Windows upon system restart, preventing any PII caching.*
