from flask import Flask, render_template, request, jsonify, redirect, session, url_for, flash, abort
from services.google_sheet_service import add_leave, get_all_leaves, get_leaves_by_month, delete_leave, get_leave_summary_by_month, get_leave_summary_by_person
import os
from dotenv import load_dotenv
from services.auth_service import create_user, authenticate_user
from services.data_service import save_leave_to_db
from models import db, User, Leave
import uuid
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from services.telegram_service import send_telegram_message


app = Flask(__name__)
load_dotenv()

# --- Critical env checks ---
app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY is not set")

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
@app.get("/health")
def health():
    return "ok", 200


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
            login_user(user) # ✅ ใช้ login_user แทน session
            flash("Logged in successfully.")
            return redirect("/")
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

# หน้า Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()   # ✅ ใช้ logout_user
    flash("You have been logged out.")
    return redirect("/login")

@app.route("/")
@login_required
def index():
    return render_template("index.html")

# หน้า forgot password
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form["username"]
        user = User.query.filter_by(username=username).first()

        if user:
            user.reset_token = str(uuid.uuid4()) # สร้าง UUID token แบบสุ่ม
            db.session.commit()
            reset_url = f"{app.config['BASE_URL'].rstrip('/')}/reset/{user.reset_token}"  # ลิงก์ reset
            flash(f"Send this link to reset: {reset_url}")  # แจ้งผู้ใช้
        else:
            flash("User not found.")

    return render_template("forgot_password.html")  # แสดงฟอร์มให้ใส่ username

# หน้า reset pasword
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    if not user:
        flash("Invalid or expired token.")
        return redirect("/login")

    if request.method == "POST":
        password = request.form["password"]
        user.set_password(password)  # แฮชรหัสผ่านใหม่
        user.reset_token = None  # เคลียร์ token เพื่อความปลอดภัย
        db.session.commit()
        flash("Password reset successful.")
        return redirect("/login")

    return render_template("reset_password.html", token=token)

# หน้า admin
@app.route("/admin")
@login_required
def admin():
    if not getattr(current_user, "is_admin", False):
        flash("Access denied.")
        return redirect("/")
    users = User.query.all()
    return render_template("admin.html", users=users)

@app.route("/admin/delete/<int:user_id>", methods=["POST"])  # ควรใช้ POST (TODo: เพิ่ม CSRF ในฟอร์ม)
@login_required
def delete_user(user_id):
    if not getattr(current_user, "is_admin", False):
        flash("Access denied.")
        return redirect("/")
    user = db.session.get(User, user_id) or abort(404)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted.")
    return redirect("/admin")

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
    save_leave_to_db(
        data["name"],
        data["leave_type"],
        data["start_date"],
        data["end_date"],
        data.get("note", ""),
    )

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)  # เปลี่ยนพอร์ตเป็น 5001