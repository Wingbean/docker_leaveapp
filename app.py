from flask import Flask, render_template, request, jsonify, redirect, session, url_for, flash, abort, current_app
from services.google_sheet_service import add_leave, get_all_leaves, get_leaves_by_month, delete_leave, get_leave_summary_by_month, get_leave_summary_by_person
import os
from dotenv import load_dotenv
from services.auth_service import create_user, authenticate_user, send_verification_email, send_password_reset_email
from services.data_service import save_leave_to_db
from services.report_service import run_report_and_push
from models import db, User, Leave
import uuid
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, generate_csrf, CSRFError
from services.telegram_service import send_telegram_message
from sqlalchemy import text

app = Flask(__name__)
load_dotenv()

# --- Critical env checks ---
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY is not set")

# ----- CSRF -----
app.config.update({
    "WTF_CSRF_TIME_LIMIT": 3600,           # โทเค็นมีอายุ 1 ชม.
    "SESSION_COOKIE_SAMESITE": "Lax",
    "SESSION_COOKIE_SECURE": True,         # ใช้ True เมื่อรันผ่าน HTTPS จริง
    "REMEMBER_COOKIE_SECURE": True,
})

csrf = CSRFProtect()
csrf.init_app(app)

@app.context_processor                   # [ADD]
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

# [แนะนำ] หน้า error สวย ๆ เวลา CSRF ไม่ผ่าน
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    # ถ้ายังไม่มี template แยก จะส่งข้อความตรง ๆ ก็ได้
    return (f"CSRF validation failed: {e.description}", 400)


MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_DB = os.getenv("MYSQL_DB")
if not all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_DB]):
    raise RuntimeError("Missing one of MYSQL_USER/MYSQL_PASSWORD/MYSQL_HOST/MYSQL_DB")

# --- DB config ---
# ระบุไดรเวอร์ mysqldb (mysqlclient) + charset ให้ชัด
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+mysqldb://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
    "?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
#app.config["ENV"] = os.getenv("FLASK_ENV", "production")

# ให้ต่อ DB ทน ๆ
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}

# เพิ่ม config สำหรับ SMTP
app.config["EMAIL_FROM"] = os.getenv("EMAIL_FROM")
app.config["EMAIL_PASSWORD"] = os.getenv("EMAIL_PASSWORD")
app.config["BASE_URL"] = os.getenv("BASE_URL", "http://localhost:5001") # ใช้สำหรับสร้างลิงก์ยืนยัน

# Cookie hardening (ถ้าอยู่หลัง reverse proxy HTTPS ควรเปิด Secure)
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
app.config.setdefault("SESSION_COOKIE_SECURE", True)        # ตั้ง True ถ้าใช้ HTTPS
app.config.setdefault("REMEMBER_COOKIE_SECURE", True)       # ตั้ง True ถ้าใช้ HTTPS

app.config["REPORT_SPREADSHEET_ID"] = os.getenv("REPORT_SPREADSHEET_ID")
app.config["REPORT_WORKSHEET"] = os.getenv("REPORT_WORKSHEET")

db.init_app(app)
migrate = Migrate(app, db) # <--- เพิ่มบรรทัดนี้

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # ถ้ายังไม่ login จะ redirect ไปที่ /login

# บอก Flask-Login ว่าจะโหลด user จาก id ด้วยฟังก์ชันไหน
@login_manager.user_loader
def load_user(user_id):
    # ใช้ API สมัยใหม่ของ SQLAlchemy 2.x
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None

# ------------------------------
# Healthcheck (ไม่ต้องล็อกอิน)
# ------------------------------
@app.route("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok}), (200 if db_ok else 503)


# ------------------------------
# Routes
# ------------------------------

# หน้า register
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":  # เมื่อกด submit form
        username = request.form["username"]  # ดึงค่าจาก input
        email = request.form["email"]
        password = request.form["password"]

        if User.query.filter_by(username=username).first():  # ตรวจสอบว่ามี username นี้แล้วหรือยัง
            flash("Username already exists.")  # แจ้งเตือน
            return redirect("/register")  # ส่งกลับไปยังฟอร์มเดิม
        if User.query.filter_by(email=email).first():
            flash("Email already registered.")
            return redirect("/register")

        create_user(username, email, password)
        flash("ลงทะเบียนสำเร็จ โปรดตรวจสอบอีเมลเพื่อยืนยัน")
        return redirect("/login")

    return render_template("register.html")  # GET -> แสดงฟอร์มลงทะเบียน

@app.route("/verify/<token>")
def verify_email(token):
    user = User.query.filter_by(verify_token=token).first()
    if not user:
        flash("ลิงก์ยืนยันไม่ถูกต้อง")
        return redirect("/login")

    user.is_verified = True
    user.verify_token = None
    db.session.commit()
    flash("ยืนยันอีเมลเรียบร้อยแล้ว กรุณาเข้าสู่ระบบ")
    return redirect("/login")


# หน้า Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = authenticate_user(request.form["username"], request.form["password"])
        if user:
            login_user(user)
            flash("เข้าสู่ระบบสำเร็จ", "success")
            return redirect(url_for("index"))
        # ไม่บอกละเอียดเกินไป: ปลอดภัยกว่า + ครอบคลุมเคสยังไม่ยืนยันอีเมล
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง หรือยังไม่ได้ยืนยันอีเมล", "danger")
        return redirect(url_for("login"))  # PRG: กันกด refresh แล้วฟอร์มส่งซ้ำ

    # GET: แสดงหน้า login เฉย ๆ (ข้อความจะมาจาก flash ใน base.html)
    return render_template("login.html")

# หน้า Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("ออกจากระบบแล้ว", "info")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("index.html")

# หน้า forgot password
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form["username"].strip()
        user = User.query.filter_by(username=username).first()

        if not user:
            flash("ไม่พบบัญชีผู้ใช้", "danger")
            return render_template("forgot_password.html")

        # ออกโทเค็นใหม่ทุกครั้ง
        user.reset_token = str(uuid.uuid4())
        db.session.commit()

        try:
            send_password_reset_email(user)  # [ADD] ส่งอีเมลจริง
            flash("ส่งลิงก์รีเซ็ตรหัสผ่านไปยังอีเมลของคุณแล้ว", "info")
        except Exception:
            # กันพัง: ถ้าส่งอีเมลไม่ได้ ยังบอกลิงก์ให้ใช้งานได้ทันที
            app.logger.exception("Failed to send reset email")
            reset_url = f"{app.config['BASE_URL'].rstrip('/')}/reset/{user.reset_token}"
            flash(f"อีเมลส่งไม่สำเร็จ แต่คุณสามารถใช้ลิงก์นี้แทน: {reset_url}", "warning")

    return render_template("forgot_password.html")


# หน้า reset pasword
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user:
        flash("Invalid or expired token.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        pwd = request.form.get("password", "").strip()
        if len(pwd) < 8:
            flash("รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร", "danger")
            return redirect(url_for("reset_password", token=token))

        try:
            user.set_password(pwd)
            user.reset_token = None
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("เกิดข้อผิดพลาดกับฐานข้อมูล", "danger")
            return redirect(url_for("reset_password", token=token))

        flash("ตั้งรหัสผ่านใหม่เรียบร้อยแล้ว", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token)

#---------------#
#   หน้า admin   #
#---------------#
@app.route("/admin")
@login_required
def admin():
    if not getattr(current_user, "is_admin", False):
        flash("Access denied.")
        return redirect("/")
    users = User.query.all()
    return render_template("admin.html", users=users)

@app.route("/admin/delete/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    # กันลบตัวเอง
    if current_user.id == user_id:
        flash("ไม่สามารถลบบัญชีของตัวเองได้", "warning")
        return redirect(url_for("admin"))

    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash("ไม่สามารถลบผู้ดูแลระบบได้", "warning")
        return redirect(url_for("admin"))

    try:
        db.session.delete(user)
        db.session.commit()
        flash("ลบผู้ใช้เรียบร้อย", "success")
    except Exception:
        db.session.rollback()
        flash("ลบไม่สำเร็จ (ปัญหาฐานข้อมูล)", "danger")

    return redirect(url_for("admin"))

@app.route("/admin/resend-verify/<int:user_id>", methods=["POST"])
@login_required
def admin_resend_verify(user_id):
    if not current_user.is_admin:
        flash("Access denied.", "danger"); return redirect(url_for("index"))
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        flash("ผู้ใช้นี้ยืนยันอีเมลแล้ว", "info")
        return redirect(url_for("admin"))
    try:
        # ถ้าเคยมี verify_token อยู่แล้ว ใช้อันเดิม; ถ้าไม่มีก็ออกใหม่
        if not user.verify_token:
            user.verify_token = str(uuid.uuid4())
            db.session.commit()
        send_verification_email(user)
        flash("ส่งลิงก์ยืนยันใหม่แล้ว", "success")
    except Exception as e:
        current_app.logger.exception(e)
        flash("ส่งลิงก์ไม่สำเร็จ", "danger")
    return redirect(url_for("admin"))

@app.route("/admin/force-reset/<int:user_id>", methods=["POST"])
@login_required
def admin_force_reset(user_id):
    if not current_user.is_admin:
        flash("Access denied.", "danger"); return redirect(url_for("index"))
    user = User.query.get_or_404(user_id)
    try:
        user.reset_token = str(uuid.uuid4())
        db.session.commit()
        reset_url = f"{current_app.config['BASE_URL'].rstrip('/')}/reset/{user.reset_token}"
        # โปรดักชัน: ส่งอีเมล reset ให้ user.email; ตอนนี้ log ไว้พอ
        current_app.logger.info("Force reset for user_id=%s: %s", user.id, reset_url)
        flash("ออกลิงก์รีเซ็ตรหัสผ่านแล้ว", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(e)
        flash("ทำรายการไม่สำเร็จ", "danger")
    return redirect(url_for("admin"))

@app.route("/admin/toggle-admin/<int:user_id>", methods=["POST"])
@login_required
def admin_toggle_admin(user_id):
    if not current_user.is_admin:
        flash("Access denied.", "danger"); return redirect(url_for("index"))
    if current_user.id == user_id:
        flash("ไม่สามารถเปลี่ยนสิทธิ์ของตัวเองได้", "warning")
        return redirect(url_for("admin"))

    user = User.query.get_or_404(user_id)
    # กัน demote จนเหลือ admin คนเดียว
    admins = User.query.filter_by(is_admin=True).all()
    if user.is_admin and len(admins) <= 1:
        flash("ไม่สามารถถอนสิทธิ์แอดมินคนสุดท้ายได้", "warning")
        return redirect(url_for("admin"))

    try:
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(("เลื่อนเป็นแอดมิน" if user.is_admin else "ถอนสิทธิ์แอดมิน") + "เรียบร้อย", "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(e)
        flash("ทำรายการไม่สำเร็จ", "danger")
    return redirect(url_for("admin"))

# Export CSV
@app.route("/admin/export/users.csv")
@login_required
def export_users_csv():
    if not current_user.is_admin:
        flash("Access denied.", "danger"); return redirect(url_for("index"))

    import csv
    from io import StringIO
    si = StringIO()
    w = csv.writer(si)
    w.writerow(["id", "username", "email", "is_verified", "is_admin"])
    for u in User.query.order_by(User.id.asc()).all():
        w.writerow([u.id, u.username, u.email, int(u.is_verified), int(u.is_admin)])

    from flask import Response
    return Response(
        si.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=users.csv"}
    )


#---------------#
#   END admin   #
#---------------#

# ลบบัญชีตัวเอง
@app.route("/delete_account", methods=["POST"])  # ควรใช้ POST (TODo: เพิ่ม CSRF ในฟอร์ม)
@login_required
def delete_account():
    db.session.delete(current_user)
    db.session.commit()
    flash("Account deleted.")
    return redirect("/login")

#--------------จัดการ Form--------------------#

@app.route("/submit", methods=["POST"])
@login_required
def submit():
    data = request.form
    
    add_leave(
        
        data["name"],
        data["leave_type"],
        data["start_date"],
        data["end_date"],
        data.get("note", ""),
    )

    # เพิ่มการบันทึกลง MySQL
    try:
        save_leave_to_db(
            data["name"], 
            data["leave_type"], 
            data["start_date"], 
            data["end_date"], 
            data.get("note",""),
        )
    except ValueError as e:
        return jsonify({"status":"error","message":str(e)}), 400
    except Exception:
        return jsonify({"status":"error","message":"DB error"}), 500

    # ✅ ส่ง Telegram Notification
    msg = (
        f"📢 <b>แจ้งเตือนบันทึกการลา</b>\n"
        f"👤 <b>ชื่อ:</b> {data['name']}\n"
        f"📝 <b>ประเภท:</b> {data['leave_type']}\n"
        f"📅 <b>ช่วง:</b> {data['start_date']} ถึง {data['end_date']}\n"
        f"🗒️ <b>หมายเหตุ:</b> {data.get('note', '-')}"
    )
    send_telegram_message(msg)

    return jsonify({"status": "success"})

@app.route("/data")
@login_required
def data():
    return jsonify(get_all_leaves())

@app.route("/calendar")
@login_required
def calendar():
    month = request.args.get("month")  # format: YYYY-MM
    return jsonify(get_leaves_by_month(month))

@app.route("/delete", methods=["POST"])
@login_required
def delete():
    data = request.json or {}
    timestamp = data.get("timestamp")
    code = data.get("code")
    success = delete_leave(timestamp, code)
    return jsonify({"success": success})

#------Dashboard------#
@app.route("/dashboard")
@login_required
def dashboard():
    monthly_summary = get_leave_summary_by_month()
    person_summary = get_leave_summary_by_person()
    return render_template("dashboard.html",
                           monthly_summary=monthly_summary,
                           person_summary=person_summary)

#----------------------#
# Route Module อื่น     #
#----------------------#
@app.route("/pedx/upload", methods=["GET", "POST"])
@login_required
def pedx_upload():
    # แนะนำ: จำกัดเฉพาะ admin
    if not getattr(current_user, "is_admin", False):
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        start_date = (request.form.get("start_date") or "").strip()
        if not start_date:
            flash("กรุณาเลือกระบุวันที่เริ่มต้น", "warning")
            return render_template("pedx.html")

        try:
            result = run_report_and_push(start_date)
            flash(f"อัปโหลดสำเร็จ: {result['rows']} แถว", "success")
        except Exception as e:
            # log จริงก็ได้: app.logger.exception(e)
            flash(f"อัปโหลดล้มเหลว: {e}", "danger")

        return redirect(url_for("pedx_upload"))

    # GET
    return render_template("pedx.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)  # เปลี่ยนพอร์ตเป็น 5001