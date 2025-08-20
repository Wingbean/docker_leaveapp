import os
import gspread
import mysql.connector
from oauth2client.service_account import ServiceAccountCredentials

# โหลดค่า env
HOSXP = {
    "host": os.getenv("HOSXP_HOST", ""),
    "port": int(os.getenv("HOSXP_PORT", "3306")),
    "user": os.getenv("HOSXP_USER", ""),
    "password": os.getenv("HOSXP_PASSWORD", ""),
    "database": os.getenv("HOSXP_DATABASE", ""),
}
SPREADSHEET_ID = os.getenv("REPORT_SPREADSHEET_ID")
WORKSHEET_NAME = os.getenv("REPORT_WORKSHEET")
GOOGLE_SA_FILE = os.getenv("GOOGLE_SA_FILE", "dataslothy-365d6e2908af.json")

# SQL อยู่ฝั่ง server เพื่อลดความเสี่ยง ไม่รับจาก client
SQL_TEMPLATE = """
SELECT
    o.vn AS 'VN'
    ,MAX(o.hn) AS 'HN'
    ,MAX(o.an) AS 'AN'
    ,MAX(o.vstdate) AS 'VstDate'
    ,MAX(o.vsttime) AS 'VstTime'
    ,MAX(ou.name) AS 'ผู้ซักประวัติ'
    ,MAX(o.doctor) AS 'รหัสแพทย์'
    ,MAX(d.name) AS 'ชื่อแพทย์'
    ,MAX(os.pe) AS 'PE'
    ,MAX(od.diag_text) AS 'Dx_Text'
    ,MAX(os.cc) AS 'CC'
    ,MAX(os.hpi) AS 'Hpi'
    ,MAX(v.pdx) AS 'PDx'
    ,MAX(v.dx1) AS 'Dx1'
    ,MAX(v.dx2) AS 'Dx2'
    ,MAX(v.dx3) AS 'Dx3'
FROM ovst o
LEFT OUTER JOIN opdscreen os ON o.vn = os.vn
LEFT OUTER JOIN doctor d  ON o.doctor = d.code
LEFT OUTER JOIN screen_doctor sd on sd.vn = o.vn
LEFT OUTER JOIN opduser ou on ou.loginname = sd.staff
LEFT OUTER JOIN vn_stat v on v.vn = o.vn
LEFT OUTER JOIN ovst_doctor_diag od on od.vn = o.vn
WHERE o.vstdate BETWEEN %s AND CURDATE()
GROUP BY o.vn
ORDER BY MAX(o.vstdate) DESC, MAX(o.vsttime) DESC, MAX(o.doctor) DESC;
""".strip()


def _gs_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SA_FILE, scope)
    return gspread.authorize(creds)


def _col_letter(n: int) -> str:
    # 1 -> A, 26 -> Z, 27 -> AA ...
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def run_report_and_push(start_date: str) -> dict:
    """
    รัน query จาก start_date แล้วอัปโหลดผลลัพธ์ (ไม่มี header) ลง worksheet ชื่อ WORKSHEET_NAME
    เคลียร์ข้อมูลเก่าตั้งแต่แถว 2 ลงไป (เก็บหัวตารางเดิมไว้)
    """
    # 1) Query DB
    conn = None
    try:
        conn = mysql.connector.connect(
            host=HOSXP["host"], port=HOSXP["port"],
            user=HOSXP["user"], password=HOSXP["password"],
            database=HOSXP["database"], charset="utf8", use_pure=True,
            connection_timeout=10, autocommit=True,
        )
        cur = conn.cursor()
        cur.execute(SQL_TEMPLATE, (start_date,))
        rows = cur.fetchall()  # list[tuple]
    finally:
        try:
            if conn and conn.is_connected():
                cur.close(); conn.close()
        except Exception:
            pass

    # 2) เข้าถึงชีต
    gc = _gs_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)

    # 3) เคลียร์ข้อมูลเดิม (แถว 2 ลงไป)
    # 3) เคลียร์ข้อมูลเดิม (แถว 2 ลงไป) — ใช้ row_count เพื่อลดการอ่านทั้งชีต
    last_row = ws.row_count
    col_count = len(rows[0]) if rows else 26  # ถ้าอยากแม่นยำขึ้น ใช้ len(ws.row_values(1)) แทน 26 ได้
    last_col_letter = _col_letter(col_count)
    if last_row > 1:
        ws.batch_clear([f"A2:{last_col_letter}{last_row}"])


    # 4) แปลงผลลัพธ์เป็น list of lists (string)
    payload = [list(map(lambda x: "" if x is None else str(x), r)) for r in rows]
    if payload:
        # [CHANGE] เขียนเป็นก้อนเล็ก ๆ เพื่อลดเวลาต่อรีเควสต์ และเลี่ยง timeout/429
        CHUNK = 500  # ลอง 200–1000 ตามขนาดข้อมูลจริง
        for i in range(0, len(payload), CHUNK):
            block = payload[i:i+CHUNK]
            ws.append_rows(block, value_input_option="USER_ENTERED")

    return {"rows": len(payload)}

