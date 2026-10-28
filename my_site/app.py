from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import secrets
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# ==================== داده‌های موقت (در حافظه) ====================
# در پروژه واقعی از دیتابیس استفاده کنید
ADMIN_USER = "admin"
ADMIN_PASS = "el123."

users = {
    # username: {"password": ..., "role": "teacher"/"student", "name": ...}
}

classrooms = {}  # class_id: {"teacher": ..., "students": [...], "raised_hands": [...], "messages": [...]}
current_sessions = {}  # username: class_id


def login_required(role=None):
    def wrapper(fn):
        def inner(*args, **kwargs):
            if "username" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role and session.get("role") != "admin":
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        inner.__name__ = fn.__name__
        return inner
    return wrapper


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # ورود ادمین
        if username == ADMIN_USER and password == ADMIN_PASS:
            session["username"] = username
            session["role"] = "admin"
            session["name"] = "مدیر سایت"
            return redirect(url_for("dashboard"))

        # ورود معلم یا دانش‌آموز
        if username in users and users[username]["password"] == password:
            session["username"] = username
            session["role"] = users[username]["role"]
            session["name"] = users[username]["name"]
            if users[username]["role"] == "teacher":
                return redirect(url_for("dashboard"))
            else:
                return redirect(url_for("student_class"))

        error = "نام کاربری یا رمز عبور اشتباه است."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==================== داشبورد ادمین/معلم ====================
@app.route("/dashboard")
@login_required()
def dashboard():
    if session["role"] == "admin":
        teachers = {u: d for u, d in users.items() if d["role"] == "teacher"}
        students = {u: d for u, d in users.items() if d["role"] == "student"}
        return render_template("dashboard.html", teachers=teachers, students=students,
                               role="admin", classrooms=classrooms)
    elif session["role"] == "teacher":
        my_class = None
        for cid, c in classrooms.items():
            if c["teacher"] == session["username"]:
                my_class = cid
                break
        return render_template("dashboard.html", role="teacher", my_class=my_class,
                               classrooms=classrooms, users=users)
    return redirect(url_for("student_class"))


@app.route("/add_user", methods=["GET", "POST"])
@login_required("admin")
def add_user():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()

        if not username or not password or not name or role not in ["teacher", "student"]:
            error = "همه فیلدها الزامی هستند."
        elif username in users or username == ADMIN_USER:
            error = "این نام کاربری قبلاً ثبت شده است."
        else:
            users[username] = {"password": password, "name": name, "role": role}
            return redirect(url_for("dashboard"))
    return render_template("add_user.html", error=error)


@app.route("/delete_user/<username>")
@login_required("admin")
def delete_user(username):
    if username in users:
        del users[username]
    return redirect(url_for("dashboard"))


# ==================== کلاس‌ها ====================
@app.route("/create_class", methods=["POST"])
@login_required("teacher")
def create_class():
    username = session["username"]
    # اگر از قبل کلاس دارد
    for cid, c in classrooms.items():
        if c["teacher"] == username:
            return redirect(url_for("classroom", class_id=cid))

    class_id = f"class_{username}"
    classrooms[class_id] = {
        "teacher": username,
        "teacher_name": session["name"],
        "students": [],
        "raised_hands": [],
        "messages": [],
    }
    return redirect(url_for("classroom", class_id=class_id))


@app.route("/classroom/<class_id>")
@login_required("teacher")
def classroom(class_id):
    if class_id not in classrooms:
        return redirect(url_for("dashboard"))
    c = classrooms[class_id]
    if c["teacher"] != session["username"]:
        return redirect(url_for("dashboard"))
    return render_template("classroom.html", class_id=class_id, c=c, users=users)


@app.route("/student_class")
@login_required("student")
def student_class():
    # پیدا کردن کلاسی که دانش‌آموز عضو آن است
    my_class = None
    for cid, c in classrooms.items():
        if session["username"] in c["students"]:
            my_class = cid
            break

    if not my_class:
        # دانش‌آموز بدون کلاس - لیست کلاس‌های موجود
        return render_template("student_class.html", my_class=None, classrooms=classrooms)

    return render_template("student_class.html", my_class=my_class,
                           classrooms=classrooms, c=classrooms[my_class])


@app.route("/join_class/<class_id>")
@login_required("student")
def join_class(class_id):
    if class_id in classrooms:
        if session["username"] not in classrooms[class_id]["students"]:
            classrooms[class_id]["students"].append(session["username"])
    return redirect(url_for("student_class"))


@app.route("/leave_class/<class_id>")
@login_required("student")
def leave_class(class_id):
    if class_id in classrooms:
        if session["username"] in classrooms[class_id]["students"]:
            classrooms[class_id]["students"].remove(session["username"])
        if session["username"] in classrooms[class_id]["raised_hands"]:
            classrooms[class_id]["raised_hands"].remove(session["username"])
    return redirect(url_for("student_class"))


# ==================== API ها ====================
@app.route("/api/raise_hand/<class_id>", methods=["POST"])
@login_required("student")
def raise_hand(class_id):
    if class_id in classrooms:
        c = classrooms[class_id]
        if session["username"] in c["students"]:
            if session["username"] not in c["raised_hands"]:
                c["raised_hands"].append(session["username"])
                return jsonify({"ok": True, "raised": True})
    return jsonify({"ok": False})


@app.route("/api/lower_hand/<class_id>", methods=["POST"])
@login_required("student")
def lower_hand(class_id):
    if class_id in classrooms:
        c = classrooms[class_id]
        if session["username"] in c["raised_hands"]:
            c["raised_hands"].remove(session["username"])
        return jsonify({"ok": True, "raised": False})
    return jsonify({"ok": False})


@app.route("/api/approve_hand/<class_id>/<username>", methods=["POST"])
@login_required("teacher")
def approve_hand(class_id, username):
    if class_id in classrooms:
        c = classrooms[class_id]
        if c["teacher"] == session["username"]:
            if username in c["raised_hands"]:
                c["raised_hands"].remove(username)
            return jsonify({"ok": True})
    return jsonify({"ok": False})


@app.route("/api/status/<class_id>")
@login_required()
def status(class_id):
    if class_id in classrooms:
        c = classrooms[class_id]
        return jsonify({
            "students": c["students"],
            "raised_hands": c["raised_hands"],
            "teacher_name": c["teacher_name"],
        })
    return jsonify({"students": [], "raised_hands": []})


@app.route("/api/send_message/<class_id>", methods=["POST"])
@login_required()
def send_message(class_id):
    if class_id in classrooms:
        c = classrooms[class_id]
        msg = request.form.get("message", "").strip()
        if msg:
            c["messages"].append({
                "from": session["name"],
                "role": session["role"],
                "text": msg,
                "time": datetime.now().strftime("%H:%M"),
            })
            if len(c["messages"]) > 50:
                c["messages"] = c["messages"][-50:]
        return jsonify({"ok": True})
    return jsonify({"ok": False})


@app.route("/api/messages/<class_id>")
@login_required()
def get_messages(class_id):
    if class_id in classrooms:
        return jsonify({"messages": classrooms[class_id]["messages"]})
    return jsonify({"messages": []})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)