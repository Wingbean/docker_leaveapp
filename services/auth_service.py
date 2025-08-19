from models import db, User  # นำเข้าจาก models.py
from flask import current_app
from uuid import uuid4
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

def send_verification_email(user) -> bool:
    token = user.verify_token
    email = user.email.strip()
    base = (current_app.config.get("BASE_URL") or "").rstrip("/")
    link = f"{base}/verify/{token}"

    msg = MIMEText(f"กรุณาคลิกลิงก์เพื่อยืนยันอีเมล: <a href=\"{link}\">{link}</a>", "html", "utf-8")
    msg["Subject"] = "ยืนยันอีเมล"
    msg["From"] = formataddr(("ระบบจองวันลา", current_app.config["EMAIL_FROM"]))
    msg["To"] = email

    host = current_app.config.get("SMTP_HOST", "smtp.gmail.com")
    port = int(current_app.config.get("SMTP_PORT", 465))
    timeout = float(current_app.config.get("SMTP_TIMEOUT", 10.0))

    try:
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
            smtp.login(current_app.config["EMAIL_FROM"], current_app.config["EMAIL_PASSWORD"])
            smtp.send_message(msg)
        return True
    except Exception:
        current_app.logger.exception("send_verification_email failed")
        return False

def create_user(username, email, password, is_admin=False):
    username = username.strip()
    email = email.strip().lower()  # ปกติ email ไม่ case-sensitive
    user = User(username=username, email=email, is_admin=is_admin)     # สร้าง object User โดยใส่ username
    user.set_password(password)        # เรียกใช้ method จาก User เพื่อ hash password
    user.verify_token = str(uuid4())

    db.session.add(user)               # ใส่ object นี้ลง session (ยังไม่บันทึกจริง)
    db.session.commit()               # บันทึกลงฐานข้อมูลจริง

    # ไม่ให้การส่งอีเมลพังทั้ง request: log แล้วให้ไปกด "ส่งใหม่" ภายหลังถ้าจำเป็น
    send_verification_email(user)

def authenticate_user(username, password):
    username = (username or "").strip()
    user = User.query.filter_by(username=username).first() # ค้นหาผู้ใช้จากฐานข้อมูล
    if user and user.check_password(password) and user.is_verified: # ถ้ามี user และ password ถูกต้อง
        return user                           # คืนค่าผู้ใช้นั้นกลับไป
    return None                               # ถ้าไม่ถูกต้อง คืน None

def send_password_reset_email(user):  # [ADD]
    token = user.reset_token
    base = current_app.config["BASE_URL"].rstrip("/")
    link = f"{base}/reset/{token}"

    html = f"""
    <p>กรุณาคลิกลิงก์เพื่อรีเซ็ตรหัสผ่าน:</p>
    <p><a href="{link}">{link}</a></p>
    <p>หากไม่ได้ร้องขอ คุณสามารถเพิกเฉยอีเมลนี้ได้</p>
    """

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = "รีเซ็ตรหัสผ่าน (Leave App)"
    msg["From"] = formataddr(("Leave App", current_app.config["EMAIL_FROM"]))
    msg["To"] = user.email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(current_app.config["EMAIL_FROM"], current_app.config["EMAIL_PASSWORD"])
        smtp.send_message(msg)
