#!/usr/bin/env python3
"""Collect daily Kiwoom trading-value leaders and build weekly sector totals.

Important limitation:
ka10032 is a trading-value ranking API, not a complete all-listed-stock dump.
This collector sums the daily ranking rows returned by Kiwoom. Stocks outside
the returned ranking on a given day are not included for that day.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"
WEEKLY_FILE = DATA_DIR / "weekly.json"
SECTORS_FILE = ROOT / "sectors.csv"

BASE_URL = "https://api.kiwoom.com"
TOKEN_URL = f"{BASE_URL}/oauth2/token"
RANK_URL = f"{BASE_URL}/api/dostk/rkinfo"
SEOUL = ZoneInfo("Asia/Seoul")
REQUEST_DELAY = 0.25
MAX_PAGES = 10


def number(value) -> int:
    if value is None:
        return 0
    raw = str(value).strip().replace(",", "").replace("+", "")
    if not raw:
        return 0
    try:
        return abs(int(float(raw)))
    except ValueError:
        return 0


def load_sector_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not SECTORS_FILE.exists():
        return mapping
    with SECTORS_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = str(row.get("code", "")).strip().zfill(6)
            sector = str(row.get("sector", "")).strip()
            if code and sector:
                mapping[code] = sector
    return mapping


def get_token(session: requests.Session) -> str:
    app_key = os.environ.get("KIWOOM_APP_KEY", "").strip()
    secret_key = os.environ.get("KIWOOM_SECRET_KEY", "").strip()
    if not app_key or not secret_key:
        raise RuntimeError("GitHub Secrets KIWOOM_APP_KEY / KIWOOM_SECRET_KEY가 설정되지 않았습니다.")
    response = session.post(
        TOKEN_URL,
        headers={"Content-Type": "application/json;charset=UTF-8"},
        json={
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": secret_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("return_code") not in (None, 0, "0"):
        raise RuntimeError(f"키움 토큰 발급 실패: {payload.get('return_msg', payload)}")
    token = payload.get("token")
    if not token:
        raise RuntimeError(f"키움 토큰 응답에 token이 없습니다: {payload}")
    return token


def fetch_market(session: requests.Session, token: str, market_code: str) -> list[dict]:
    all_rows: list[dict] = []
    cont_yn, next_key = "N", ""
    for page in range(MAX_PAGES):
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "api-id": "ka10032",
            "cont-yn": cont_yn,
            "next-key": next_key,
        }
        body = {
            "mrkt_tp": market_code,       # 001: KOSPI, 101: KOSDAQ
            "mang_stk_incls": "0",        # exclude managed stocks
            "stex_tp": "3",               # integrated exchange
        }
        response = session.post(RANK_URL, headers=headers, json=body, timeout=45)
        response.raise_for_status()
        payload = response.json()
        rc = payload.get("return_code")
        if rc not in (None, 0, "0"):
            raise RuntimeError(
                f"ka10032 오류({market_code}): {payload.get('return_msg', payload)}"
            )
        rows = payload.get("trde_prica_upper", [])
        if not isinstance(rows, list):
            raise RuntimeError(f"ka10032 응답 형식이 예상과 다릅니다: {list(payload.keys())}")
        all_rows.extend(r for r in rows if isinstance(r, dict))

        cont_yn = response.headers.get("cont-yn", "N")
        next_key = response.headers.get("next-key", "")
        if cont_yn != "Y" or not next_key:
            break
        time.sleep(REQUEST_DELAY)
    return all_rows


def make_daily_snapshot(trading_date: date, sector_map: dict[str, str]) -> dict:
    session = requests.Session()
    token = get_token(session)
    combined: list[dict] = []
    for market_code, market_name in (("001", "KOSPI"), ("101", "KOSDAQ")):
        raw_rows = fetch_market(session, token, market_code)
        for row in raw_rows:
            code = str(row.get("stk_cd", "")).strip().replace("A", "").zfill(6)
            if not code or code == "000000":
                continue
            combined.append({
                "market": market_name,
                "code": code,
                "name": str(row.get("stk_nm", "")).strip(),
                "sector": sector_map.get(code, "미분류"),
                "value": number(row.get("trde_prica")),
                "rank": number(row.get("now_rank")),
                "change_rate": str(row.get("flu_rt", "")).strip(),
            })
    # If the same code appears more than once, retain the largest value row.
    unique: dict[tuple[str, str], dict] = {}
    for item in combined:
        key = (item["market"], item["code"])
        if key not in unique or item["value"] > unique[key]["value"]:
            unique[key] = item
    stocks = sorted(unique.values(), key=lambda x: x["value"], reverse=True)
    return {
        "date": trading_date.isoformat(),
        "source": "Kiwoom REST API ka10032",
        "scope_note": "당일 거래대금 상위 API 응답 종목만 포함. 전체 상장종목 전수 합계가 아닙니다.",
        "stocks": stocks,
    }


def iso_week_id(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def week_label(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}년 {w}주차"


def read_daily_files() -> list[dict]:
    records = []
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(DAILY_DIR.glob("????-??-??.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            print(f"경고: 읽을 수 없는 일별 파일 건너뜀: {path}", file=sys.stderr)
    return records


def build_weekly(daily_records: list[dict], today: date) -> dict:
    grouped: dict[str, dict[tuple[str, str], dict]] = defaultdict(dict)
    week_days: dict[str, set[str]] = defaultdict(set)
    for record in daily_records:
        try:
            d = date.fromisoformat(record["date"])
        except (KeyError, ValueError, TypeError):
            continue
        wid = iso_week_id(d)
        week_days[wid].add(d.isoformat())
        for stock in record.get("stocks", []):
            key = (stock.get("market", ""), stock.get("code", ""))
            if not key[1]:
                continue
            target = grouped[wid].setdefault(key, {
                "market": key[0],
                "code": key[1],
                "name": stock.get("name", ""),
                "sector": stock.get("sector") or "미분류",
                "value": 0,
                "days": 0,
            })
            target["value"] += int(stock.get("value", 0) or 0)
            target["days"] += 1
            if stock.get("name"):
                target["name"] = stock["name"]
            if stock.get("sector") and stock["sector"] != "미분류":
                target["sector"] = stock["sector"]

    current_id = iso_week_id(today)
    previous_id = iso_week_id(today - timedelta(days=7))
    previous_values = {
        key: item["value"] for key, item in grouped.get(previous_id, {}).items()
    }

    weeks = []
    for wid in sorted(grouped.keys(), reverse=True)[:26]:
        stocks = []
        for key, item in grouped[wid].items():
            stocks.append({
                "market": item["market"],
                "code": item["code"],
                "name": item["name"],
                "sector": item["sector"],
                "value": item["value"],
                "prev_value": previous_values.get(key, 0) if wid == current_id else 0,
                "days_seen": item["days"],
            })
        stocks.sort(key=lambda x: x["value"], reverse=True)
        y, w = map(int, wid.split("-W"))
        week_start = date.fromisocalendar(y, w, 1)
        week_end = date.fromisocalendar(y, w, 5)
        weeks.append({
            "id": wid,
            "label": week_label(week_start),
            "period": f"{week_start.isoformat()} ~ {week_end.isoformat()}",
            "days_collected": len(week_days[wid]),
            "stocks": stocks,
        })

    return {
        "updated_at": datetime.now(SEOUL).strftime("%Y-%m-%d %H:%M:%S KST"),
        "source": "Kiwoom REST API ka10032",
        "scope_note": "매일 거래대금 상위 API에 노출된 종목의 일별 거래대금을 합산한 값입니다. 상위권 밖 종목은 해당 일자 합산에서 빠질 수 있으며, 섹터는 sectors.csv 매핑 기준입니다.",
        "weeks": weeks,
    }


def main() -> None:
    today = datetime.now(SEOUL).date()
    # Workflow is scheduled after the Korean market close on weekdays.
    sector_map = load_sector_map()
    snapshot = make_daily_snapshot(today, sector_map)
    if not snapshot["stocks"]:
        raise RuntimeError("키움 API에서 종목 데이터가 0건 반환됐습니다. 배포하지 않습니다.")

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = DAILY_DIR / f"{today.isoformat()}.json"
    daily_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    weekly = build_weekly(read_daily_files(), today)
    WEEKLY_FILE.write_text(
        json.dumps(weekly, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"수집 완료: {today} / {len(snapshot['stocks'])}개 종목")
    print(f"주간 파일 갱신: {WEEKLY_FILE}")


if __name__ == "__main__":
    main()
