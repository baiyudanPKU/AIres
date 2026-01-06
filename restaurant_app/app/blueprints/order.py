import decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from flask_login import login_required, current_user
from sqlalchemy import func, desc

from app import db
from app.models import Restaurant, Category, Dish, Order, OrderItem, ChatMessage, Blacklist

bp = Blueprint("order", __name__, url_prefix="/order")


def _get_cart():
    cart = session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
    return cart


def _save_cart(cart):
    session["cart"] = cart
    session.modified = True


@bp.get("/")
@login_required
def list_restaurants():
    sales_sum = func.coalesce(func.sum(Order.total_amount), 0).label("sales")
    rows = (
        db.session.query(Restaurant, sales_sum)
        .outerjoin(Order, Order.restaurant_id == Restaurant.id)
        .group_by(Restaurant.id)
        .order_by(desc("sales"), Restaurant.id.asc())
        .all()
    )
    return render_template("order/restaurants.html", rows=rows)


@bp.get("/<int:restaurant_id>")
@login_required
def restaurant_menu(restaurant_id):
    r = Restaurant.query.get_or_404(restaurant_id)

    # 黑名单拦截
    bl = Blacklist.query.filter_by(restaurant_id=restaurant_id, user_id=current_user.id).first()
    if bl:
        flash("你已被该餐厅拉黑，无法点餐", "danger")
        return redirect(url_for("order.list_restaurants"))
    cats = Category.query.filter_by(restaurant_id=r.id).order_by(Category.id.asc()).all()
    dishes_all = Dish.query.filter_by(restaurant_id=r.id).order_by(Dish.id.desc()).all()

    selected_cat = request.args.get("cat", type=int)
    cat_ids = [c.id for c in cats]
    if not selected_cat or selected_cat not in cat_ids:
        selected_cat = cat_ids[0] if cat_ids else None

    dishes_map = {}
    for d in dishes_all:
        dishes_map.setdefault(d.category_id, []).append(d)

    cart = _get_cart().get(str(r.id), {})
    cart_count = sum(cart.values()) if isinstance(cart, dict) else 0

    return render_template(
        "order/restaurant.html",
        restaurant=r,
        categories=cats,
        dishes_map=dishes_map,
        cart_count=cart_count,
        selected_cat=selected_cat,
    )


@bp.get("/<int:restaurant_id>/dish/<int:dish_id>")
@login_required
def dish_detail(restaurant_id, dish_id):
    r = Restaurant.query.get_or_404(restaurant_id)

    bl = Blacklist.query.filter_by(restaurant_id=restaurant_id, user_id=current_user.id).first()
    if bl:
        flash("你已被该餐厅拉黑，无法查看菜品详情", "danger")
        return redirect(url_for("order.list_restaurants"))
    dish = Dish.query.filter_by(id=dish_id, restaurant_id=r.id).first_or_404()

    chats = (
        ChatMessage.query.filter_by(restaurant_id=r.id, dish_id=dish.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
        .all()
    )
    chats = list(reversed(chats))

    return render_template(
        "order/dish_detail.html",
        restaurant=r,
        dish=dish,
        chats=chats,
    )


@bp.post("/<int:restaurant_id>/add")
@login_required
def add_to_cart(restaurant_id):
    bl = Blacklist.query.filter_by(restaurant_id=restaurant_id, user_id=current_user.id).first()
    if bl:
        flash("你已被该餐厅拉黑，无法点餐", "danger")
        return redirect(url_for("order.list_restaurants"))
    dish_id = request.form.get("dish_id")
    cat_id = request.form.get("cat_id")
    try:
        dish_id_int = int(dish_id)
    except Exception:
        abort(400)

    dish = Dish.query.filter_by(id=dish_id_int, restaurant_id=restaurant_id).first()
    if not dish:
        abort(404)

    try:
        cat_id_int = int(cat_id)
    except Exception:
        cat_id_int = dish.category_id

    qty = request.form.get("quantity", "1")
    try:
        qty_int = max(1, int(qty))
    except Exception:
        qty_int = 1

    cart = _get_cart()
    rest_key = str(restaurant_id)
    rest_cart = cart.get(rest_key, {}) if isinstance(cart.get(rest_key), dict) else {}
    rest_cart[str(dish_id_int)] = rest_cart.get(str(dish_id_int), 0) + qty_int
    cart[rest_key] = rest_cart
    _save_cart(cart)

    flash(f"已加入餐桌：{dish.name} × {qty_int}", "success")
    return redirect(
        url_for("order.restaurant_menu", restaurant_id=restaurant_id, cat=cat_id_int)
    )


@bp.get("/cart/<int:restaurant_id>")
@login_required
def view_cart(restaurant_id):
    r = Restaurant.query.get_or_404(restaurant_id)

    bl = Blacklist.query.filter_by(restaurant_id=restaurant_id, user_id=current_user.id).first()
    if bl:
        flash("你已被该餐厅拉黑，无法查看餐桌", "danger")
        return redirect(url_for("order.list_restaurants"))
    cart = _get_cart().get(str(restaurant_id), {})
    if not isinstance(cart, dict):
        cart = {}

    dish_ids = [int(did) for did in cart.keys()]
    dishes = (
        Dish.query.filter(Dish.restaurant_id == restaurant_id, Dish.id.in_(dish_ids)).all()
        if dish_ids
        else []
    )

    items = []
    total = decimal.Decimal("0")
    for d in dishes:
        qty = cart.get(str(d.id), 0)
        line_total = (d.price or decimal.Decimal("0")) * qty
        total += line_total
        items.append({"dish": d, "qty": qty, "line_total": line_total})

    return render_template("order/cart.html", restaurant=r, items=items, total=total)


@bp.post("/cart/<int:restaurant_id>/update")
@login_required
def update_cart(restaurant_id):
    dish_id = request.form.get("dish_id")
    action = request.form.get("action", "").lower()
    try:
        dish_id_int = int(dish_id)
    except Exception:
        abort(400)

    cart = _get_cart()
    rest_key = str(restaurant_id)
    rest_cart = cart.get(rest_key, {}) if isinstance(cart.get(rest_key), dict) else {}

    if str(dish_id_int) not in rest_cart:
        return redirect(url_for("order.view_cart", restaurant_id=restaurant_id))

    if action == "inc":
        rest_cart[str(dish_id_int)] += 1
    elif action == "dec":
        rest_cart[str(dish_id_int)] = max(0, rest_cart[str(dish_id_int)] - 1)
    elif action == "remove":
        rest_cart[str(dish_id_int)] = 0

    rest_cart = {k: v for k, v in rest_cart.items() if v > 0}
    if rest_cart:
        cart[rest_key] = rest_cart
    else:
        cart.pop(rest_key, None)

    _save_cart(cart)
    return redirect(url_for("order.view_cart", restaurant_id=restaurant_id))


@bp.post("/cart/<int:restaurant_id>/checkout")
@login_required
def checkout(restaurant_id):
    r = Restaurant.query.get_or_404(restaurant_id)

    bl = Blacklist.query.filter_by(restaurant_id=restaurant_id, user_id=current_user.id).first()
    if bl:
        flash("你已被该餐厅拉黑，无法下单", "danger")
        return redirect(url_for("order.list_restaurants"))
    cart = _get_cart().get(str(restaurant_id), {})
    if not isinstance(cart, dict) or not cart:
        flash("餐桌里还没有菜品", "warning")
        return redirect(url_for("order.view_cart", restaurant_id=restaurant_id))

    dish_ids = [int(did) for did in cart.keys()]
    dishes = Dish.query.filter(Dish.restaurant_id == restaurant_id, Dish.id.in_(dish_ids)).all()
    if not dishes:
        flash("餐桌里的菜品不存在或已下架", "danger")
        return redirect(url_for("order.view_cart", restaurant_id=restaurant_id))

    total = decimal.Decimal("0")
    order = Order(user_id=current_user.id, restaurant_id=restaurant_id, total_amount=0)
    db.session.add(order)
    db.session.flush()

    for d in dishes:
        qty = cart.get(str(d.id), 0)
        if qty <= 0:
            continue
        line_total = (d.price or decimal.Decimal("0")) * qty
        total += line_total
        db.session.add(
            OrderItem(order_id=order.id, dish_id=d.id, quantity=qty, unit_price=d.price)
        )

    order.total_amount = total
    db.session.commit()

    cart_all = _get_cart()
    cart_all.pop(str(restaurant_id), None)
    _save_cart(cart_all)

    flash(f"付款成功，感谢用餐！本次消费 ¥{total:.2f}", "success")
    return render_template("order/checkout_success.html", restaurant=r, total=total)


@bp.post("/<int:restaurant_id>/dish/<int:dish_id>/ask")
@login_required
def ask_dish(restaurant_id, dish_id):
    r = Restaurant.query.get_or_404(restaurant_id)
    dish = Dish.query.filter_by(id=dish_id, restaurant_id=r.id).first_or_404()
    question = (request.form.get("question", "") or "").strip()
    if not question:
        flash("请先输入想问的问题", "warning")
        return redirect(url_for("order.dish_detail", restaurant_id=r.id, dish_id=dish.id))

    related_dish = dish
    all_dishes = Dish.query.filter_by(restaurant_id=r.id).all()
    q_lower = question.lower()
    for d in all_dishes:
        if d.id == dish.id:
            continue
        if d.name and d.name.lower() in q_lower:
            related_dish = d
            break

    db.session.add(
        ChatMessage(
            restaurant_id=r.id,
            user_id=current_user.id,
            dish_id=related_dish.id,
            role="user",
            scene="dish",
            content=question,
        )
    )

    answer_parts = [f"关于 {related_dish.name} 的信息:"]
    if related_dish.description:
        answer_parts.append(related_dish.description[:160])
    answer_parts.append(f"价格：¥{related_dish.price}")
    answer = "\n".join(answer_parts)

    db.session.add(
        ChatMessage(
            restaurant_id=r.id,
            user_id=current_user.id,
            dish_id=related_dish.id,
            role="assistant",
            scene="dish",
            content=answer,
        )
    )
    db.session.commit()

    flash("已回答你的提问，见下方对话", "info")
    return redirect(url_for("order.dish_detail", restaurant_id=r.id, dish_id=related_dish.id))
