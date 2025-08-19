from models import db, Leave
from datetime import date
from flask import current_app

def save_leave_to_db(name, leave_type, start_date, end_date, note) -> int:
    # normalize input
    name = (name or "").strip()
    leave_type = (leave_type or "").strip()
    note = (note or "").strip()[:100]  # schema จำกัด 100

    # parse & validate dates
    try:
        sd = date.fromisoformat(str(start_date))
        ed = date.fromisoformat(str(end_date))
    except ValueError as e:
        # โยน error ชัดเจนให้ route จัดการตอบ 400
        raise ValueError("start_date/end_date ต้องเป็นรูปแบบ YYYY-MM-DD") from e

    if sd > ed:
        raise ValueError("ช่วงวันลาไม่ถูกต้อง: start_date > end_date")

    leave = Leave(
        name=name,
        leave_type=leave_type,
        start_date=sd,
        end_date=ed,
        note=note,
        # timestamp ไม่ต้องใส่ DB จะเติม CURRENT_TIMESTAMP ให้เอง
    )

    try:
        db.session.add(leave)
        db.session.commit()
        return leave.id
    except Exception:
        db.session.rollback()
        current_app.logger.exception("save_leave_to_db failed")
        # ส่งต่อให้ route ตอบ 500 หรือจับทำเป็นข้อความได้
        raise