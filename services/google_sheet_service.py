import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
# print("SPREADSHEET_ID =", SPREADSHEET_ID)
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets"]
creds = ServiceAccountCredentials.from_json_keyfile_name("dataslothy-365d6e2908af.json", SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_key(SPREADSHEET_ID).sheet1  # เปิด sheet แรก

def add_leave(name, leave_type, start_date, end_date, note,):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [timestamp, name, leave_type, start_date, end_date, note]
    sheet.append_row(row)

def get_all_leaves():
    rows = sheet.get_all_values()
    headers = rows[0]
    data = rows[1:]
    return [dict(zip(headers, row)) for row in data]

def get_leaves_by_month(month):  # month format: "2025-06"
    data = get_all_leaves()
    result = []
    for row in data:
        if row["Start Date"].startswith(month) or row["End Date"].startswith(month):
            result.append(row)
    return result

def delete_leave(timestamp, code):
    sheet_data = sheet.get_all_values()
    header = sheet_data[0]
    rows = sheet_data[1:]

    try:
        ts_idx = header.index("Timestamp")
        code_idx = header.index("code")
    except ValueError:
        return False  # Column not found

    for i, row in enumerate(rows):
        if len(row) > ts_idx and row[ts_idx] == timestamp:
            if len(row) > code_idx and row[code_idx] == code:
                sheet.delete_rows(i + 2)  # +2 because of header + 0-based index
                return True
            else:
                return False  # code ไม่ตรง
    return False  # timestamp ไม่พบ

#---ส่วนการดึง dashboard---------#
def get_all_data():
    values = sheet.get_all_values()
    headers = values[0]
    data = values[1:]

    result = []
    for row in data:
        item = dict(zip(headers, row))
        result.append(item)
    return result


def get_leave_summary_by_month():
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


def get_leave_summary_by_person():
    rows = get_all_data()
    person_counts = defaultdict(int)

    for row in rows:
        name = row.get("Name", "").strip()
        if name:
            person_counts[name] += 1

    return [{"name": name, "total": count} for name, count in sorted(person_counts.items(), key=lambda x: x[1], reverse=True)]