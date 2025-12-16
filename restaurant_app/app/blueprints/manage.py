import os
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user

from app import db
from app.models import Restaurant, Category, Dish
from app.utils.images import save_image

bp = Blueprint("manage", __name__, url_prefix="/manage")

DEFAULT_CATEGORIES = ["菜品", "主食", "甜品", "饮品"]


def _get_my_restaurant():
    """当前登录用户管理的餐厅（每个用户最多一个）"""
    return Restaurant.query.filter_by(manager_id=current_user.id).first()


@bp.get("/")
@login_required
def index():
    r = _get_my_restaurant()
    if not r:
        return redirect(url_for("manage.create_restaurant"))

    cats = Category.query.filter_by(restaurant_id=r.id).order_by(Category.id.asc()).all()
    
    dishes_all = Dish.query.filter_by(restaurant_id=r.id).order_by(Dish.id.desc()).all()
    dishes_map = {}
    for d in dishes_all:
        dishes_map.setdefault(d.category_id, []).append(d)

    return render_template("manage/index.html", restaurant=r, categories=cats, dishes_map=dishes_map)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_restaurant():
    existing = _get_my_restaurant()
    if existing:
        return redirect(url_for("manage.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        logo = request.files.get("logo")

        if not name:
            flash("餐厅名不能为空", "danger")
            return render_template("manage/create_restaurant.html")

        if Restaurant.query.filter_by(name=name).first():
            flash("餐厅名已存在，请换一个", "danger")
            return render_template("manage/create_restaurant.html")

        if not logo or logo.filename == "":
            flash("请上传餐厅 Logo", "danger")
            return render_template("manage/create_restaurant.html")

        # 保存 logo（缩略到 100x100 内）
        base_upload = current_app.config["UPLOAD_DIR"]  # .../app/static/uploads
        logo_dir_abs = os.path.join(base_upload, "restaurants")
        try:
            out_name = save_image(logo, logo_dir_abs, max_size=(100, 100))
            logo_rel = f"uploads/restaurants/{out_name}"
        except Exception as e:
            flash(f"Logo 上传失败：{e}", "danger")
            return render_template("manage/create_restaurant.html")

        r = Restaurant(name=name, logo_path=logo_rel, manager_id=current_user.id)
        db.session.add(r)
        db.session.flush()  # 先拿到 r.id

        # 自动生成 4 个分类
        for c in DEFAULT_CATEGORIES:
            db.session.add(Category(restaurant_id=r.id, name=c))

        db.session.commit()
        flash("餐厅创建成功，已自动生成分类", "success")
        return redirect(url_for("manage.index"))

    return render_template("manage/create_restaurant.html")


@bp.route("/category/<int:category_id>/dishes/new", methods=["GET", "POST"])
@login_required
def add_dish(category_id):
    r = _get_my_restaurant()
    if not r:
        return redirect(url_for("manage.create_restaurant"))

    cat = Category.query.filter_by(id=category_id, restaurant_id=r.id).first()
    if not cat:
        abort(404)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        price_str = request.form.get("price", "").strip()
        desc = request.form.get("description", "").strip()
        image = request.files.get("image")

        # 校验
        if not name:
            flash("菜品名称不能为空", "danger")
            return render_template("manage/add_dish.html", restaurant=r, category=cat)

        if len(desc) == 0 or len(desc) > 500:
            flash("菜品介绍不能为空，且不得超过 500 字", "danger")
            return render_template("manage/add_dish.html", restaurant=r, category=cat)

        try:
            price = Decimal(price_str)
            if price <= 0:
                raise InvalidOperation()
        except Exception:
            flash("价格格式不正确（例如 12.50），且必须大于 0", "danger")
            return render_template("manage/add_dish.html", restaurant=r, category=cat)

        if not image or image.filename == "":
            flash("必须上传菜品图片（系统会自动缩略到 100×100 内）", "danger")
            return render_template("manage/add_dish.html", restaurant=r, category=cat)

        # 同餐厅菜品名不可重复
        if Dish.query.filter_by(restaurant_id=r.id, name=name).first():
            flash("该餐厅已存在同名菜品，请换一个名称", "danger")
            return render_template("manage/add_dish.html", restaurant=r, category=cat)

        # 保存图片（缩略到<=100x100）
        try:
            base_upload = current_app.config["UPLOAD_DIR"]
            dish_dir_abs = os.path.join(base_upload, "dishes")
            out_name = save_image(image, dish_dir_abs, max_size=(100, 100))
            image_rel = f"uploads/dishes/{out_name}"
        except Exception as e:
            flash(f"图片处理失败：{e}", "danger")
            return render_template("manage/add_dish.html", restaurant=r, category=cat)

        dish = Dish(
            restaurant_id=r.id,
            category_id=cat.id,
            name=name,
            price=price,
            description=desc,
            image_path=image_rel,
        )
        db.session.add(dish)
        db.session.commit()

        flash("菜品添加成功", "success")
        return redirect(url_for("manage.index"))

    return render_template("manage/add_dish.html", restaurant=r, category=cat)


@bp.post("/dish/<int:dish_id>/delete")
@login_required
def delete_dish(dish_id):
    r = _get_my_restaurant()
    if not r:
        return redirect(url_for("manage.create_restaurant"))

    dish = Dish.query.filter_by(id=dish_id, restaurant_id=r.id).first()
    if not dish:
        abort(404)

    db.session.delete(dish)   # ⭐如果模型外键/relationship配置好了，会自动级联删相关记录
    db.session.commit()

    flash(f"已删除菜品：{dish.name}", "success")
    return redirect(url_for("manage.index"))
