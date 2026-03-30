# GDT Edge Hub

Local service for **Modbus RTU** polling, **SQLite** persistence, and batched upload to the **GDT Console** (Vercel). The UI is served at `http://127.0.0.1:8756` by default.

## Requirements

- Python 3.11+
- Windows or Linux with a serial port (RS485 adapter)

## Install

```bash
cd edge-hub
python -m venv .venv
```

Then install with the venv’s interpreter (works without activating):

- **Windows:** `.venv\Scripts\python.exe -m pip install -r requirements.txt`
- **Linux / macOS:** `.venv/bin/python -m pip install -r requirements.txt`

Or activate the venv and run `pip install -r requirements.txt` as usual.

Activate the venv if you prefer:

- **Linux / macOS:** `source .venv/bin/activate`
- **Windows cmd:** `.venv\Scripts\activate.bat`
- **Windows PowerShell:** if `Activate.ps1` is blocked by execution policy, use **`.venv\Scripts\activate.bat`** or run Python without activating (below).

## Run

```bash
python run.py
```

**Windows (no activation):** `.\.venv\Scripts\python.exe run.py` or double-click **`run.cmd`** after the venv exists.

Override bind address or data directory:

```bash
set GDT_HOST=0.0.0.0
set GDT_PORT=8756
set GDT_HUB_DATA=C:\ProgramData\GDT\hub
python run.py
```

Data (SQLite) defaults to `edge-hub/data/hub.db`.

## Sites and reactors

- Load sites from the console, optionally filter with the search box, then **choose a site**.
- That triggers `POST /api/local-reactors/sync` with `{ "site_id": N }`, which mirrors console reactors into SQLite (and drops local rows that no longer exist on the console for that site).
- You **cannot** add reactors manually; Modbus devices are configured per mirrored reactor on the **Reactors** tab.
- Modbus polling only runs reactors for the **currently selected site** (`selected_site_id` in settings).

## Console API (to implement on Next.js)

The hub calls these routes with `Authorization: Bearer <api_key>`:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/ingest/v1/sites` | List sites `{ id, slug, name }` |
| GET | `/api/ingest/v1/sites/{site_id}/reactors` | List reactors `{ id, name, site_id }` |
| POST | `/api/ingest/v1/readings` | Batch body `{ "readings": [ ... ] }` |

Each reading object should match:

```json
{
  "reactor_id": 12,
  "reading_at": "2025-03-25T12:00:00+00:00",
  "temperature_c": 24.5,
  "ph": 7.1,
  "ph_raw": 7.1,
  "spectral": [100, 101, 102, 103, 104, 105, 106, 107, 108],
  "spectral_status": 0
}
```

Set **`GDT_INGEST_API_KEY`** on the Vercel project to a long random string; paste the **same** value into the Edge Hub “API key” field. Requests use `Authorization: Bearer <key>`.

After adding the spectral table migration, run it against production (see `gdt_console/drizzle/0007_reactor_spectral_readings.sql`).

## Device presets

- **ph_temp** — CWT-BL style pH + temperature (holding registers 0–1, FC3).
- **spectral** — AS7341 board (spectral block + status word; same as legacy PyQt app).
- **custom** — JSON register list (see UI default example).

## Development

The app stack is **FastAPI**, **SQLAlchemy 2**, **minimalmodbus**, **httpx**.

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8756
```
