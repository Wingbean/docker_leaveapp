from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy import CheckConstraint, Index, func

# หมายเหตุ: เก็บเวลาเป็น UTC ใน DB แล้วค่อยแปลงเป็น Asia/Bangkok ตอนแสดงผล

db = SQLAlchemy() # ใช้เชื่อมต่อและควบคุมฐานข้อมูล

class User(db.Model, UserMixin): # สร้าง model ชื่อ User (แทน table ในฐานข้อมูล)
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True) # คอลัมน์ id เป็น primary key
    username = db.Column(db.String(50), unique=True, nullable=False) # คอลัมน์ชื่อผู้ใช้
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False) # คอลัมน์เก็บรหัสผ่านแบบ hash แล้ว
    is_admin = db.Column(db.Boolean, nullable=False, server_default=db.text("0"))  # ระบุว่าเป็น admin หรือไม่ (True/False) ค่า default คือ False
    is_verified = db.Column(db.Boolean, nullable=False, server_default=db.text("0"))  # เพิ่มสถานะยืนยันอีเมล
    verify_token = db.Column(db.String(100), nullable=True)  # token สำหรับยืนยัน
    reset_token = db.Column(db.String(100), nullable=True)  # Token ใช้ reset password (optional)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")
				# แปลง password ธรรมดาให้เป็น hash แบบปลอดภัย

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
        # ตรวจว่า password ที่กรอกมาตรงกับ hash เดิมไหม

    def __repr__(self) -> str:
        return f"<User '{self.username}'>"

#  --- เพิ่ม Model ใหม่ที่นี่ --- 
class Leave(db.Model):
    __tablename__ = "leave"

    id = db.Column(db.Integer, primary_key=True)    
    #timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(ZoneInfo("Asia/Bangkok")))
    # เก็บเป็น UTC ใน DB; ใช้ DEFAULT ฝั่ง DB ให้แน่ใจว่ามีค่าเสมอ
    timestamp = db.Column(
        db.DateTime, nullable=False, server_default=func.now()
    )
    name = db.Column(db.String(100), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(100), nullable=False)

    __table_args__ = (
        # กันช่วงลาผิดตรรกะ
        CheckConstraint("start_date <= end_date", name="ck_leave_date_range"),
        # ดัชนีที่ช่วยคิวรีรายชื่อ/ช่วงวันที่
        Index("ix_leave_name_dates", "name", "start_date", "end_date"),
        # ดัชนีสำหรับหน้า dashboard/order ล่าสุด
        Index("ix_leave_timestamp_desc", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"Leave(name='{self.name}', type='{self.leave_type}', start='{self.start_date}')"
