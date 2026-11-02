import csv, json, os, time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "data" / "daily"
WEEKLY = ROOT / "data" / "weekly.json"
SECTORS = ROOT / "sectors.csv"
BASE = "https://api.kiwoom.com"
SEOUL = ZoneInfo("Asia/Seoul")

def as_int(value):
    try:
        return abs(int(float(str(value or "0").replace(",", "").replace("+", "").strip())))
    except (TypeError, ValueError):
        return 0

def sector_map():
    result = {}
    if SECTORS.exists():
        with SECTORS.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                code = str(row.get("code", "")).strip().zfill(6)
                if code:
                    result[code] = row.get("sector", "").strip() or "미분류"
    return result

def get_token(s):
    appkey = os.environ["KIWOOM_APP_KEY"].strip()
    secretkey = os.environ["KIWOOM_SECRET_KEY"].strip()
    r = s.post(BASE + "/oauth2/token",
        headers={"Content-Type": "application/json;charset=UTF-8"},
        json={"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
        timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("return_code") not in (None, 0, "0") or not data.get("token"):
        raise RuntimeError("키움 토큰 발급 실패: " + str(data))
    return data["token"]

def fetch_rank(s, token, market):
    result, cont, key = [], "N", ""
    for _ in range(10):
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": "Bearer " + token,
            "api-id": "ka10032",
            "cont-yn": cont,
            "next-key": key
        }
        body = {"mrkt_tp": market, "mang_stk_incls": "0", "stex_tp": "3"}
        r = s.post(BASE + "/api/dostk/rkinfo", headers=headers, json=body, timeout=45)
        r.raise_for_status()
        data = r.json()
        if data.get("return_code") not in (None, 0, "0"):
            raise RuntimeError("ka10032 오류: " + str(data.get("return_msg", data)))
        rows = data.get("trde_prica_upper", [])
        if not isinstance(rows, list):
            raise RuntimeError("거래대금 응답 형식이 예상과 다릅니다.")
        result.extend(x for x in rows if isinstance(x, dict))
        cont = r.headers.get("cont-yn", "N")
        key = r.headers.get("next-key", "")
        if cont != "Y" or not key:
            break
        time.sleep(0.25)
    return result

def iso_week(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"

def collect():
    today = datetime.now(SEOUL).date()
    s = requests.Session()
    token = get_token(s)
    sectors = sector_map()
    stocks = []
    for market_code, market_name in (("001", "KOSPI"), ("101", "KOSDAQ")):
        for row in fetch_rank(s, token, market_code):
            code = str(row.get("stk_cd", "")).strip().replace("A", "").zfill(6)
            if not code or code == "000000":
                continue
            stocks.append({
                "market": market_name, "code": code,
                "name": str(row.get("stk_nm", "")).strip(),
                "sector": sectors.get(code, "미분류"),
                "value": as_int(row.get("trde_prica")),
                "rank": as_int(row.get("now_rank"))
            })
    if not stocks:
        raise RuntimeError("키움 API가 종목 0건을 반환했습니다. 데이터 파일을 갱신하지 않습니다.")
    unique = {}
    for x in stocks:
        k = (x["market"], x["code"])
        if k not in unique or x["value"] > unique[k]["value"]:
            unique[k] = x
    DAILY.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "date": today.isoformat(),
        "source": "Kiwoom REST API ka10032",
        "scope_note": "당일 거래대금 상위 API 응답 종목만 포함합니다. 전 종목 전수 데이터가 아닙니다.",
        "stocks": sorted(unique.values(), key=lambda x: x["value"], reverse=True)
    }
    (DAILY / f"{today.isoformat()}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_week, days = defaultdict(dict), defaultdict(set)
    for path in sorted(DAILY.glob("????-??-??.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        d = date.fromisoformat(rec["date"])
        wid = iso_week(d)
        days[wid].add(rec["date"])
        for x in rec.get("stocks", []):
            k = (x["market"], x["code"])
            item = by_week[wid].setdefault(k, {
                "market": x["market"], "code": x["code"], "name": x["name"],
                "sector": x.get("sector") or "미분류", "value": 0, "days_seen": 0
            })
            item["value"] += int(x.get("value", 0))
            item["days_seen"] += 1
            if x.get("sector") and x["sector"] != "미분류":
                item["sector"] = x["sector"]
            if x.get("name"):
                item["name"] = x["name"]

    this_week = iso_week(today)
    prev_week = iso_week(today - timedelta(days=7))
    prev = {k: v["value"] for k, v in by_week.get(prev_week, {}).items()}
    weeks = []
    for wid in sorted(by_week, reverse=True)[:26]:
        year, week = map(int, wid.split("-W"))
        monday = date.fromisocalendar(year, week, 1)
        friday = date.fromisocalendar(year, week, 5)
        rows = []
        for k, x in by_week[wid].items():
            rows.append({
                **x,
                "prev_value": prev.get(k, 0) if wid == this_week else 0
            })
        rows.sort(key=lambda x: x["value"], reverse=True)
        weeks.append({
            "id": wid, "label": f"{year}년 {week}주차",
            "period": f"{monday.isoformat()} ~ {friday.isoformat()}",
            "days_collected": len(days[wid]), "stocks": rows
        })
    output = {
        "updated_at": datetime.now(SEOUL).strftime("%Y-%m-%d %H:%M:%S KST"),
        "source": "Kiwoom REST API ka10032",
        "scope_note": "매일 거래대금 상위 API 응답 종목의 거래대금을 주간 합산합니다. 상위권 밖 종목은 해당 일자 합계에서 빠질 수 있습니다. 섹터는 sectors.csv 매핑 기준입니다.",
        "weeks": weeks
    }
    WEEKLY.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"수집 성공: {today}, {len(snapshot['stocks'])}개 종목")

if __name__ == "__main__":
    collect()
