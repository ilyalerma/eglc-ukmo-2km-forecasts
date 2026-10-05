#!/usr/bin/env python3
"""
Download UKMO UKV 2km daily-max forecasts at fixed lead times (1, 2, 3 days).

Output columns (long format, one row per target day × lead):
  target_date, lead_days, issue_date, issue_time, temperature_2m_max_c, ...

Two Open-Meteo sources (see README):
  - Single Runs API: London 00:00 issue, leads 1–3 (from ~2026-04-02).
  - Previous Runs API: lead 1 only via hourly _previous_day1 (from ~2025-01-01).
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

# London City Airport (EGLC)
ICAO = "EGLC"
LAT = 51.504797
LON = 0.051542
MODEL = "ukmo_uk_deterministic_2km"
TZ = "Europe/London"
LEADS = (1, 2, 3)

SINGLE_RUNS_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = "ukmo_2km_lead_forecasts.csv"

SINGLE_RUNS_FROM = date(2026, 4, 2)
PREVIOUS_RUNS_FROM = date(2025, 1, 1)
CHUNK_DAYS = 90
FORECAST_HOURS = 192
REQUEST_PAUSE_S = 0.15


def _daily_max_from_hourly(times: list, temps: list) -> dict[date, float]:
    df = pd.DataFrame({"time": pd.to_datetime(times), "t": temps})
    df["d"] = df["time"].dt.date
    return df.groupby("d")["t"].max().to_dict()


def fetch_single_run_leads(issue_date: date) -> list[dict]:
    """Forecast issued at issue_date 00:00 Europe/London; targets issue+N."""
    run = f"{issue_date.isoformat()}T00:00"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "run": run,
        "forecast_hours": FORECAST_HOURS,
        "hourly": "temperature_2m",
        "timezone": TZ,
        "models": MODEL,
    }
    resp = requests.get(SINGLE_RUNS_URL, params=params, timeout=120)
    data = resp.json()
    if data.get("error"):
        logging.warning("Single run %s: %s", issue_date, data.get("reason"))
        return []

    hourly = data.get("hourly") or {}
    daily_max = _daily_max_from_hourly(hourly.get("time", []), hourly.get("temperature_2m", []))
    issue_time = f"{issue_date.isoformat()}T00:00"
    rows = []
    for lead in LEADS:
        target = issue_date + timedelta(days=lead)
        tmax = daily_max.get(target)
        if tmax is None or pd.isna(tmax):
            continue
        rows.append({
            "station": ICAO,
            "target_date": target.isoformat(),
            "lead_days": lead,
            "issue_date": issue_date.isoformat(),
            "issue_time": issue_time,
            "temperature_2m_max_c": float(tmax),
            "model": MODEL,
            "source": "single_runs_london_00",
        })
    return rows


def fetch_previous_runs_chunk(start: date, end: date) -> list[dict]:
    """Lead N = max hourly temperature_2m_previous_dayN on target_date (London)."""
    cols = [f"temperature_2m_previous_day{lead}" for lead in LEADS]
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(["temperature_2m"] + cols),
        "timezone": TZ,
        "models": MODEL,
    }
    resp = requests.get(PREVIOUS_RUNS_URL, params=params, timeout=180)
    resp.raise_for_status()
    hourly = resp.json().get("hourly") or {}
    if not hourly.get("time"):
        return []

    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df["target_date"] = df["time"].dt.date

    rows: list[dict] = []
    for lead in LEADS:
        col = f"temperature_2m_previous_day{lead}"
        if col not in df.columns:
            continue
        daily = df.groupby("target_date")[col].max()
        for target, tmax in daily.items():
            if tmax is None or pd.isna(tmax):
                continue
            issue_d = target - timedelta(days=lead)
            rows.append({
                "station": ICAO,
                "target_date": target.isoformat(),
                "lead_days": lead,
                "issue_date": issue_d.isoformat(),
                "issue_time": "",
                "temperature_2m_max_c": float(tmax),
                "model": MODEL,
                "source": f"previous_runs_day{lead}",
            })
    return rows


def chunk_ranges(start: date, end: date) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        ce = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        out.append((cur, ce))
        cur = ce + timedelta(days=1)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-from", default=SINGLE_RUNS_FROM.isoformat())
    parser.add_argument("--previous-from", default=PREVIOUS_RUNS_FROM.isoformat())
    parser.add_argument("--end", default=None, help="Default: yesterday")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today() - timedelta(days=1)
    single_from = datetime.strptime(args.single_from, "%Y-%m-%d").date()
    previous_from = datetime.strptime(args.previous_from, "%Y-%m-%d").date()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []

    # Previous runs: lead 1 (and 2/3 if API ever fills them) before single-run era
    prev_end = min(end, SINGLE_RUNS_FROM - timedelta(days=1))
    if previous_from <= prev_end:
        logging.info("Previous Runs %s → %s", previous_from, prev_end)
        for a, b in chunk_ranges(previous_from, prev_end):
            chunk_rows = fetch_previous_runs_chunk(a, b)
            all_rows.extend(chunk_rows)
            logging.info("  chunk %s→%s: %d rows", a, b, len(chunk_rows))
            time.sleep(REQUEST_PAUSE_S)

    # Single runs: explicit issue at London midnight, leads 1–3
    if single_from <= end:
        logging.info("Single Runs %s → %s (one request per issue day)", single_from, end)
        d = single_from
        while d <= end:
            all_rows.extend(fetch_single_run_leads(d))
            time.sleep(REQUEST_PAUSE_S)
            if (d - single_from).days % 30 == 0:
                logging.info("  … through issue %s", d)
            d += timedelta(days=1)

    if not all_rows:
        logging.error("No rows fetched")
        return

    out = pd.DataFrame(all_rows)
    out["latitude"] = LAT
    out["longitude"] = LON
    out = out.sort_values(["target_date", "lead_days", "source"]).drop_duplicates(
        subset=["target_date", "lead_days", "source"], keep="last"
    )
    # Prefer single-run rows when both exist for same target/lead
    priority = {"single_runs_london_00": 0, "previous_runs_day1": 1, "previous_runs_day2": 2, "previous_runs_day3": 3}
    out["_pri"] = out["source"].map(priority).fillna(9)
    out = out.sort_values(["target_date", "lead_days", "_pri"]).drop_duplicates(
        subset=["target_date", "lead_days"], keep="first"
    ).drop(columns=["_pri"])

    path = DATA_DIR / OUT_FILE
    out.to_csv(path, index=False)
    logging.info("Wrote %s (%d rows)", path, len(out))
    for lead in LEADS:
        n = (out["lead_days"] == lead).sum()
        logging.info("  lead %d: %d rows", lead, n)


if __name__ == "__main__":
    main()
