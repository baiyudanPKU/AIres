import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User
from app.utils.images import save_image

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.get("/ping")
def ping():
    return "auth ok"


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        avatar = request.files.get("avatar")

        if not username:
            flash("用户名不能为空", "danger")
            return render_template("auth/register.html")
        if len(password) < 4:
            flash("密码至少 4 位", "danger")
            return render_template("auth/register.html")
        if password != confirm:
            flash("两次输入密码不一致", "danger")
            return render_template("auth/register.html")
        if User.query.filter_by(username=username).first():
            flash("用户名已存在，请换一个", "danger")
            return render_template("auth/register.html")

        # 作业要求：注册必须上传头像（<=100x100）；我们这里自动缩略到 100x100 内
        if not avatar or avatar.filename == "":
            flash("注册需要上传头像（会自动缩略到 100×100 内）", "danger")
            return render_template("auth/register.html")

        try:
            # 存到 app/static/uploads/avatars/
            base_upload = current_app.config["UPLOAD_DIR"]  # .../app/static/uploads
            avatar_dir_abs = os.path.join(base_upload, "avatars")
            out_name = save_image(avatar, avatar_dir_abs, max_size=(100, 100))
            avatar_rel = f"uploads/avatars/{out_name}"
        except Exception as e:
            flash(f"头像上传失败：{e}", "danger")
            return render_template("auth/register.html")

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            avatar_path=avatar_rel,
        )
        db.session.add(user)
        db.session.commit()

        flash("注册成功，请登录", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("用户名或密码错误", "danger")
            return render_template("auth/login.html")

        login_user(user)
        flash("登录成功", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html")


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "info")
    return redirect(url_for("auth.login"))

