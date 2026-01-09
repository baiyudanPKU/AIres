import decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort,jsonify


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
        ChatMessage.query.filter_by(
            restaurant_id=r.id,
            dish_id=dish.id,
            user_id=current_user.id,
            scene="dish"
        )
        .order_by(ChatMessage.created_at.asc())
        .limit(50)
        .all()
    )

    return render_template(
        "order/dish_detail.html",
        restaurant=r,
        dish=dish,
        chats=chats,
    )


import requests, json

def _get_dish_history(user_id, restaurant_id, dish_id, max_messages=20):
    msgs = (
        ChatMessage.query.filter_by(
            user_id=user_id,
            restaurant_id=restaurant_id,
            dish_id=dish_id,
            scene="dish"
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(max_messages)
        .all()
    )
    msgs.reverse()
    lines = []
    for m in msgs:
        ts = m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[{ts}] {m.role}: {m.content}")
    return "\n".join(lines)


def _call_ai_for_dish(user_id, restaurant, dish, question):
    # ✅ 这里复用你商家端同一套网关
    GATEWAY_BASE_URL = "https://chat.noc.pku.edu.cn"
    GATEWAY_API_KEY = "GuoWeiCourse_tGv4UT02q7q7"
    MODEL_NAME = "deepseek-v3-250324"
    API_ENDPOINT = f"{GATEWAY_BASE_URL}/v1/chat/completions"

    history = _get_dish_history(user_id, restaurant.id, dish.id)
    # ① 先查餐厅所有菜
    all_dishes = Dish.query.filter_by(restaurant_id=restaurant.id).all()

    # ② 生成 menu_text（给 AI 用）
    menu_text = "\n".join([
        f"- {d.name} ¥{float(d.price):.2f} 描述：{d.description or '（暂无）'}"
        for d in all_dishes[:30]   # 最多给 30 个，够用了
    ])

    system_content = f"""
你是一个“点餐助手”，面向普通顾客，目标是帮助顾客更快决定吃什么、怎么搭配、是否符合口味。

你已知信息（来自数据库，可能不完整）：
- 餐厅：{restaurant.name}
- 当前菜品：{dish.name}
- 价格：¥{float(dish.price):.2f}
- 菜品描述：{dish.description or "（暂无）"}

可选：餐厅菜单（用于推荐/对比）：
{menu_text}

对话历史（用于保持上下文）：
{history}

回答规则（非常重要）：
1) 允许给“通用建议”和“口味偏好引导”，但必须明确哪些是通用建议、哪些是基于已知数据。
2) 如果缺少关键事实（如辣度、甜度、食材、分量），不要直接说“无法判断”就结束；要先给一个合理的选择建议，并提出 1-2 个澄清问题让顾客补充信息。
3) 不要编造具体事实（例如“这道菜一定很辣/用了牛肉”），除非描述里明确写了。
4) 输出尽量简洁：优先 3-6 句话；必要时用小标题或短列表。
5) 语气友好自然，像真实点餐助手。
"""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GATEWAY_API_KEY}"
    }

    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question}
        ],
        "stream": True,
        "temperature": 0.6,
        "max_tokens": 600
    }

    try:
        resp = requests.post(API_ENDPOINT, headers=headers, json=data, stream=True, timeout=300)
        resp.raise_for_status()

        ai_reply = ""
        for line in resp.iter_lines():
            if not line:
                continue
            s = line.decode("utf-8")
            if not s.startswith("data: "):
                continue
            payload = s[len("data: "):].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    ai_reply += delta
            except json.JSONDecodeError:
                pass

        ai_reply = ai_reply.strip()
        return ai_reply if ai_reply else "我暂时没有生成到有效回答，可以换个问法试试。"

    except Exception:
        return "AI 暂时不可用，请稍后再试。"


@bp.post("/ask_dish/<int:restaurant_id>/<int:dish_id>")
@login_required
def ask_dish(restaurant_id, dish_id):
    r = Restaurant.query.get_or_404(restaurant_id)

    bl = Blacklist.query.filter_by(restaurant_id=restaurant_id, user_id=current_user.id).first()
    if bl:
        return jsonify({"status": "error", "msg": "你已被该餐厅拉黑，无法提问"})

    dish = Dish.query.filter_by(id=dish_id, restaurant_id=r.id).first_or_404()

    question = (request.form.get("question") or request.form.get("content") or "").strip()
    if not question:
        return jsonify({"status": "error", "msg": "问题不能为空"})

    # 1) 存用户消息
    user_msg = ChatMessage(
        restaurant_id=r.id,
        dish_id=dish.id,
        user_id=current_user.id,
        role="user",
        scene="dish",
        content=question
    )
    db.session.add(user_msg)
    db.session.commit()

    # 2) 调 AI
    ai_reply = _call_ai_for_dish(current_user.id, r, dish, question)

    # 3) 存 AI 回复
    bot_msg = ChatMessage(
        restaurant_id=r.id,
        dish_id=dish.id,
        user_id=current_user.id,
        role="assistant",
        scene="dish",
        content=ai_reply
    )
    db.session.add(bot_msg)
    db.session.commit()

    return jsonify({
        "status": "success",
        "user_msg": {
            "id": user_msg.id,
            "role": user_msg.role,
            "content": user_msg.content,
            "timestamp": user_msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        },
        "bot_msg": {
            "id": bot_msg.id,
            "role": bot_msg.role,
            "content": bot_msg.content,
            "timestamp": bot_msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    })






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


# @bp.post("/<int:restaurant_id>/dish/<int:dish_id>/ask")
# @login_required
# def ask_dish(restaurant_id, dish_id):
#     r = Restaurant.query.get_or_404(restaurant_id)
#     dish = Dish.query.filter_by(id=dish_id, restaurant_id=r.id).first_or_404()
#     question = (request.form.get("question", "") or "").strip()
#     if not question:
#         flash("请先输入想问的问题", "warning")
#         return redirect(url_for("order.dish_detail", restaurant_id=r.id, dish_id=dish.id))

#     related_dish = dish
#     all_dishes = Dish.query.filter_by(restaurant_id=r.id).all()
#     q_lower = question.lower()
#     for d in all_dishes:
#         if d.id == dish.id:
#             continue
#         if d.name and d.name.lower() in q_lower:
#             related_dish = d
#             break

#     db.session.add(
#         ChatMessage(
#             restaurant_id=r.id,
#             user_id=current_user.id,
#             dish_id=related_dish.id,
#             role="user",
#             scene="dish",
#             content=question,
#         )
#     )

#     answer_parts = [f"关于 {related_dish.name} 的信息:"]
#     if related_dish.description:
#         answer_parts.append(related_dish.description[:160])
#     answer_parts.append(f"价格：¥{related_dish.price}")
#     answer = "\n".join(answer_parts)

#     db.session.add(
#         ChatMessage(
#             restaurant_id=r.id,
#             user_id=current_user.id,
#             dish_id=related_dish.id,
#             role="assistant",
#             scene="dish",
#             content=answer,
#         )
#     )
#     db.session.commit()

#     flash("已回答你的提问，见下方对话", "info")
#     return redirect(url_for("order.dish_detail", restaurant_id=r.id, dish_id=related_dish.id))
