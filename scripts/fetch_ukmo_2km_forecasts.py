#!/usr/bin/env python3
"""Download UKMO UKV 2km historical forecasts at Heathrow into ./data/."""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

LAT = 51.4706
LON = -0.4619
MODEL = "ukmo_uk_deterministic_2km"
TZ = "Europe/London"
API = "https://historical-forecast-api.open-meteo.com/v1/forecast"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "rain_sum",
    "showers_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "cloud_cover_mean",
    "cloud_cover_max",
    "dew_point_2m_mean",
    "pressure_msl_mean",
    "shortwave_radiation_sum",
    "sunshine_duration",
]

HOURLY_VARS = ["temperature_2m", "dew_point_2m", "relative_humidity_2m"]

CHUNK_DAYS = 120
REFRESH_DAYS = 3


def chunk_ranges(start: date, end: date) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        ce = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        out.append((cur, ce))
        cur = ce + timedelta(days=1)
    return out


def _get(params: dict) -> dict:
    resp = requests.get(API, params=params, timeout=180)
    resp.raise_for_status()
    return resp.json()


def fetch_daily_range(start: date, end: date) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for a, b in chunk_ranges(start, end):
        payload = _get({
            "latitude": LAT,
            "longitude": LON,
            "start_date": a.isoformat(),
            "end_date": b.isoformat(),
            "daily": ",".join(DAILY_VARS),
            "timezone": TZ,
            "models": MODEL,
        })
        daily = payload.get("daily") or {}
        if not daily.get("time"):
            continue
        df = pd.DataFrame(daily)
        df = df.rename(columns={"time": "date"})
        df["date"] = pd.to_datetime(df["date"])
        df["model"] = MODEL
        df["latitude"] = payload.get("latitude")
        df["longitude"] = payload.get("longitude")
        frames.append(df)
        logging.info("Daily %s → %s (%d rows)", a, b, len(df))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def fetch_hourly_range(start: date, end: date) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for a, b in chunk_ranges(start, end):
        payload = _get({
            "latitude": LAT,
            "longitude": LON,
            "start_date": a.isoformat(),
            "end_date": b.isoformat(),
            "hourly": ",".join(HOURLY_VARS),
            "timezone": "UTC",
            "models": MODEL,
        })
        hourly = payload.get("hourly") or {}
        if not hourly.get("time"):
            continue
        df = pd.DataFrame(hourly)
        df = df.rename(columns={"time": "valid_utc"})
        df["valid_utc"] = pd.to_datetime(df["valid_utc"], utc=True)
        df["model"] = MODEL
        frames.append(df)
        logging.info("Hourly %s → %s (%d rows)", a, b, len(df))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(subset=["valid_utc"]).sort_values("valid_utc").reset_index(drop=True)


def merge_incremental(existing: pd.DataFrame, new: pd.DataFrame, key: str) -> pd.DataFrame:
    if existing.empty:
        return new
    if new.empty:
        return existing
    combined = pd.concat([existing, new], ignore_index=True)
    return combined.drop_duplicates(subset=[key]).sort_values(key).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default=None, help="Default: today minus 2 days")
    parser.add_argument("--full-refresh", action="store_true")
    parser.add_argument("--skip-hourly", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today() - timedelta(days=2)
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    daily_path = DATA_DIR / "ukmo_2km_daily.csv"
    hourly_path = DATA_DIR / "ukmo_2km_hourly.csv"

    fetch_start = start
    daily_existing = pd.DataFrame()
    if daily_path.exists() and not args.full_refresh:
        daily_existing = pd.read_csv(daily_path, parse_dates=["date"])
        if not daily_existing.empty:
            last = pd.Timestamp(daily_existing["date"].max()).date()
            fetch_start = max(start, last - timedelta(days=REFRESH_DAYS))
            logging.info("Daily cache through %s; fetch from %s", last, fetch_start)

    daily_new = fetch_daily_range(fetch_start, end) if fetch_start <= end else pd.DataFrame()
    daily = merge_incremental(daily_existing, daily_new, "date")
    daily.to_csv(daily_path, index=False)
    logging.info("Wrote %s (%d rows)", daily_path.name, len(daily))

    if args.skip_hourly:
        return

    hourly_existing = pd.DataFrame()
    h_fetch_start = start
    if hourly_path.exists() and not args.full_refresh:
        hourly_existing = pd.read_csv(hourly_path, parse_dates=["valid_utc"])
        if not hourly_existing.empty:
            last_h = pd.Timestamp(hourly_existing["valid_utc"].max()).date()
            h_fetch_start = max(start, last_h - timedelta(days=REFRESH_DAYS))
            logging.info("Hourly cache through %s; fetch from %s", last_h, h_fetch_start)

    hourly_new = fetch_hourly_range(h_fetch_start, end) if h_fetch_start <= end else pd.DataFrame()
    hourly = merge_incremental(hourly_existing, hourly_new, "valid_utc")
    hourly.to_csv(hourly_path, index=False)
    logging.info("Wrote %s (%d rows)", hourly_path.name, len(hourly))


if __name__ == "__main__":
    main()
