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
| `data/ukmo_2km_daily.csv` | Daily forecast fields (one row per calendar day) |
| `data/ukmo_2km_hourly.csv` | Hourly 2 m temperature and dew point (UTC timestamps) |

Values are **what the model predicted**, not observations.

**Coverage in current bundle:** daily and hourly from **2022-01-01** through **2026-10-03** (API lag ~2 days). UKMO 2 km fields are often empty before **~2022-03**; use rows with non-null `temperature_2m_max` for analysis.

## Refresh

```bash
pip install -r requirements.txt
python scripts/fetch_ukmo_2km_forecasts.py
python scripts/fetch_ukmo_2km_forecasts.py --start 2022-01-01 --full-refresh
```

Incremental runs extend existing CSVs and refresh the last few days.

## Source

Open-Meteo Historical Forecast API — free for non-commercial use; see [Open-Meteo terms](https://open-meteo.com/en/terms).
