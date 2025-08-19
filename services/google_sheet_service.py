import os
from datetime import datetime, timezone
from collections import defaultdict

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from dotenv import load_dotenv

load_dotenv()

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise RuntimeError("SPREADSHEET_ID is not set")

# SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets"]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"  # พอแล้ว ไม่ต้องใช้ feeds เก่า
]

CREDS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "dataslothy-365d6e2908af.json")

creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPES)
gc = gspread.authorize(creds)

sheet = gc.open_by_key(SPREADSHEET_ID).sheet1  # แผ่นแรก

# ---- จัดการ HEader กับ data ---- #
# เฮดเดอร์ขั้นต่ำที่คาดหวัง (ตามชีตของคุณ)
MIN_HEADERS = ["Timestamp", "Name", "Leave Type", "Start Date", "End Date", "Note"]
# ถ้ามีคอลัมน์ "code" จะใช้ประกอบการลบด้วย
OPTIONAL_HEADERS = ["code"]

def _fetch_headers_and_rows():
    rows = sheet.get_all_values()
    if not rows:
        raise RuntimeError("Sheet is empty or inaccessible")
    headers = rows[0]
    data = rows[1:]
    return headers, data

def _ensure_headers(headers):
    # กัน KeyError ด้วยการ normalize key เท่าที่ใช้
    missing = [h for h in MIN_HEADERS if h not in headers]
    if missing:
        raise RuntimeError(f"Missing required headers: {missing}")

# ---- จบ Header ----#

def add_leave(name, leave_type, start_date, end_date, note):
    # เวลาเก็บเป็น UTC ISO 8601 (Z) ให้หน้าเว็บไปแปลงเป็นเวลาไทยตอนแสดงผล
    # ⚠️ จำไว้: script.js และ _alltable.html ต้องแปลงเวลาเป็น Asia/Bangkok (ตามที่คุยกัน)
    ts_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    headers, _ = _fetch_headers_and_rows()
    _ensure_headers(headers)

    record = {
        "Timestamp": ts_utc,
        "Name": (name or "").strip(),
        "Leave Type": (leave_type or "").strip(),
        "Start Date": str(start_date).strip(),
        "End Date": str(end_date).strip(),
        "Note": (note or "").strip(),
    }

    # ถ้าชีตมีคอลัมน์ "code" ให้เติมโค้ด (ใช้ timestamp เป็นโค้ดง่าย ๆ หรือจะเปลี่ยนเป็น uuid ก็ได้)
    #if "code" in headers and "code" not in record:
    #    record["code"] = ts_utc  # หรือจะใช้ uuid4().hex ก็ได้

    # จัดเรียงค่าตามลำดับคอลัมน์จริงของชีต
    row = [record.get(h, "") for h in headers]

    # ให้ Google แปล format เอง (USER_ENTERED) หรือจะใช้ RAW ก็ได้ถ้าอยากเก็บตามสตริงเป๊ะ
    sheet.append_row(row, value_input_option="USER_ENTERED")


    #timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #row = [timestamp, name, leave_type, start_date, end_date, note]
    #sheet.append_row(row)

def get_all_leaves():
    headers, data = _fetch_headers_and_rows()
    _ensure_headers(headers)
    return [dict(zip(headers, row)) for row in data]

#def get_leaves_by_month(month):  # month format: "2025-06"
#    data = get_all_leaves()
#    result = []
#    for row in data:
#        if row["Start Date"].startswith(month) or row["End Date"].startswith(month):
#            result.append(row)
#    return result

def get_leaves_by_month(month):  # month "YYYY-MM"
    headers, data = _fetch_headers_and_rows()
    _ensure_headers(headers)
    idx = {h: i for i, h in enumerate(headers)}
    out = []
    for row in data:
        sd = row[idx["Start Date"]] if len(row) > idx["Start Date"] else ""
        ed = row[idx["End Date"]] if len(row) > idx["End Date"] else ""
        if sd.startswith(month) or ed.startswith(month):
            out.append(dict(zip(headers, row)))
    return out

def delete_leave(timestamp, code):
    headers, data = _fetch_headers_and_rows()

    # หา index ของคอลัมน์ที่ต้องใช้
    try:
        ts_idx = headers.index("Timestamp")
    except ValueError:
        return False

    code_idx = headers.index("code") if "code" in headers else None

    # หาแถวที่ตรง
    # ถ้ามีคอลัมน์ code: ต้องตรงทั้ง timestamp และ code
    # ถ้าไม่มีคอลัมน์ code: ให้ลบด้วย timestamp อย่างเดียว (ทำให้ฟังก์ชันใช้ได้กับชีตเก่าของคุณ)

    for i, row in enumerate(data, start=2):
        if len(row) <= ts_idx or row[ts_idx] != timestamp:
            continue
        if code_idx is not None:
            row_code = row[code_idx] if len(row) > code_idx else ""
            # ถ้ามีทั้ง code ที่ส่งมา และ code ในแถว → ต้องตรงกัน
            if code and row_code and row_code != code:
                continue
            # ถ้า code ฝั่งใดฝั่งหนึ่งว่าง → ยอมลบด้วย timestamp
        sheet.delete_rows(i)
        return True
    return False

#---ส่วนการดึง dashboard---------#
#def get_all_data():
    values = sheet.get_all_values()
    headers = values[0]
    data = values[1:]

    result = []
    for row in data:
        item = dict(zip(headers, row))
        result.append(item)
    return result

#def get_leave_summary_by_month():
    rows = get_all_data()
    monthly_counts = defaultdict(int)

    for row in rows:
        try:
            start_date = datetime.strptime(row["Start Date"], "%Y-%m-%d")
            key = start_date.strftime("%Y-%m")  # เช่น '2025-07'
            monthly_counts[key] += 1
        except Exception as e:
            print(f"❌ Error parsing row: {row} | {e}")
            continue

    # แปลงเป็น list ของ dict
    return [{"month": month, "total": count} for month, count in sorted(monthly_counts.items())]

#def get_leave_summary_by_person():
    rows = get_all_data()
    person_counts = defaultdict(int)

    for row in rows:
        name = row.get("Name", "").strip()
        if name:
            person_counts[name] += 1

    return [{"name": name, "total": count} for name, count in sorted(person_counts.items(), key=lambda x: x[1], reverse=True)]

def get_all_data():
    headers, data = _fetch_headers_and_rows()
    return [dict(zip(headers, row)) for row in data]

def get_leave_summary_by_month():
    rows = get_all_data()
    monthly_counts = defaultdict(int)
    for row in rows:
        try:
            sd = row.get("Start Date", "")
            # รับทั้ง "YYYY-MM-DD" หรือ "YYYY-MM-DDTHH:MM..." ก็ได้
            key = sd[:7]  # 'YYYY-MM'
            if len(key) == 7:
                monthly_counts[key] += 1
        except Exception:
            continue
    return [{"month": m, "total": c} for m, c in sorted(monthly_counts.items())]

def get_leave_summary_by_person():
    rows = get_all_data()
    person_counts = defaultdict(int)
    for row in rows:
        name = (row.get("Name") or "").strip()
        if name:
            person_counts[name] += 1
    return [
        {"name": n, "total": c}
        for n, c in sorted(person_counts.items(), key=lambda x: x[1], reverse=True)
    ]
