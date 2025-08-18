from models import db, Leave
from datetime import datetime

def save_leave_to_db(name, leave_type, start_date, end_date, note):
    leave = Leave(
        name=name,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        note=note        
    )
    db.session.add(leave)
    db.session.commit()