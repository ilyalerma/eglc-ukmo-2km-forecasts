# Heathrow UKMO UKV 2 km — historical forecasts

Stored **UK Met Office UKV 2 km** (`ukmo_uk_deterministic_2km`) forecasts at **London Heathrow (EGLL)** via the [Open-Meteo Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api).

This repo is **data only** (no verification or bias analysis).

## Location

| Field | Value |
|--------|--------|
| ICAO | EGLL (London Heathrow) |
| Latitude | 51.4706°N |
| Longitude | 0.4619°W |
| Timezone | Europe/London |
| Model | `ukmo_uk_deterministic_2km` |

Open-Meteo snaps to the nearest grid cell (~51.46°N, 0.45°W, elevation ~23 m).

## Files

| File | Description |
|------|-------------|
| `data/ukmo_2km_lead_forecasts.csv` | **Fixed-lead daily max** (1, 2, 3 days ahead) with `target_date` and `issue_date` |
| `data/ukmo_2km_daily.csv` | Stitched Historical Forecast API daily fields (valid time only; not fixed lead) |
| `data/ukmo_2km_hourly.csv` | Stitched Historical Forecast API hourly (UTC) |

### Lead forecast CSV columns

| Column | Meaning |
|--------|---------|
| `target_date` | Calendar day being forecast (**Europe/London**) |
| `lead_days` | `1`, `2`, or `3` days after `issue_date` |
| `issue_date` | Calendar day the forecast was issued (London) |
| `issue_time` | `YYYY-MM-DDT00:00` for Single Runs; empty for Previous Runs |
| `temperature_2m_max_c` | Predicted daily max (max of hourly 2 m temps on `target_date`) |
| `source` | `single_runs_london_00` or `previous_runs_dayN` |

**Coverage:**

- **Leads 1–3** from **2026-04-02** — [Single Runs API](https://open-meteo.com/en/docs/single-runs-api), model run at **London midnight** each `issue_date`. In practice Open-Meteo’s UKMO 2 km archive often has **lead 2** populated and **lead 3** missing (null forecast hours); re-fetch after Open-Meteo archive updates.
- **Lead 1 only** from **2025-01-01** to **2026-04-01** — [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) (`temperature_2m_previous_day1`; ~24 h before each valid hour). Open-Meteo does **not** archive `_previous_day2/3` for UKMO 2 km.

Values are **what the model predicted**, not observations.

**Stitched archive (`ukmo_2km_daily/hourly`):** coverage **2022-01-01** → **2026-10-03**; UKMO 2 km often empty before **~2022-03**.

## Refresh

```bash
pip install -r requirements.txt
python scripts/fetch_ukmo_2km_lead_forecasts.py
python scripts/fetch_ukmo_2km_forecasts.py
python scripts/fetch_ukmo_2km_forecasts.py --start 2022-01-01 --full-refresh
```

## Source

Open-Meteo Historical Forecast API — free for non-commercial use; see [Open-Meteo terms](https://open-meteo.com/en/terms).
