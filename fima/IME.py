import requests
import json
import pandas as pd


main_category = 0
category = 0
sub_category = 0
producer = 0
start_year = 1395
end_year = 1404

url = "https://www.ime.co.ir/subsystems/ime/services/home/imedata.asmx/GetAmareMoamelatList"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/plain, */*; q=0.01",
    "Content-Type": "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.ime.co.ir",
    "Referer": "https://www.ime.co.ir/offer-stat.html",
    "Connection": "keep-alive",
}

all_data = []

# === Define 6-month windows per year ===
for year in range(start_year, end_year + 1):
    intervals = [
        (f"{year}/1/1", f"{year}/6/31"),
        (f"{year}/7/1", f"{year}/12/29"),
    ]

    for from_date, to_date in intervals:
        payload = {
            "Language": 8,
            "fari": False,
            "GregorianFromDate": from_date,
            "GregorianToDate": to_date,
            "MainCat": main_category,
            "Cat": category,
            "SubCat": sub_category,
            "Producer": producer
        }

        print(f"📅 Fetching {from_date} → {to_date}")
        try:
            res = requests.post(url, headers=headers, json=payload)
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            continue

        if not res.ok or not res.text.strip().startswith("{"):
            print(f"❌ Server error or invalid response for {from_date} → {to_date}")
            continue

        try:
            raw_json = res.json()["d"]
            records = json.loads(raw_json)
        except Exception as e:
            print(f"❌ JSON decode failed for {from_date} → {to_date}:", e)
            continue

        if not records:
            print(f"⚠️ No records for {from_date} → {to_date}")
            continue

        all_data.extend(records)
        print(f"✅ Retrieved {len(records)} rows.")

# === Combine results ===
if all_data:
    df = pd.DataFrame(all_data)
else:
    print("❌ No data found across all 6-month intervals.")
