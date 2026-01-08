from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Restaurant, ChatMessage
from datetime import datetime
import requests
import os
import json

bp = Blueprint("advisor", __name__)

def get_user_history(restaurant_id, user_id, max_messages=20, scene="advisor"):
    """获取指定餐厅、用户和场景的对话历史"""
    messages = ChatMessage.query.filter_by(
        restaurant_id=restaurant_id, 
        user_id=user_id, 
        scene=scene
    ).order_by(ChatMessage.created_at.asc()).limit(max_messages).all()
    
    history = []
    for msg in messages:
        history.append(f"{msg.role}: {msg.content}")
    return "\n".join(history)


def get_restaurant_data(restaurant_id):
    """获取餐厅的真实数据用于AI分析"""
    from sqlalchemy import func
    from app.models import Order, OrderItem, User, Dish, Category
    
    # 获取消费最多的客户
    top_customers = db.session.query(
        User.id,
        User.username,
        func.sum(Order.total_amount).label('total_spent')
    ).join(Order).filter(
        Order.restaurant_id == restaurant_id
    ).group_by(User.id).order_by(func.sum(Order.total_amount).desc()).limit(10).all()
    
    # 获取销售最好的菜品
    top_dishes = db.session.query(
        Dish.id,
        Dish.name,
        func.sum(OrderItem.quantity).label('total_quantity'),
        func.count(OrderItem.id).label('order_count'),
        func.avg(OrderItem.unit_price).label('avg_price')
    ).join(OrderItem).join(Order).filter(
        Order.restaurant_id == restaurant_id
    ).group_by(Dish.id).order_by(func.sum(OrderItem.quantity).desc()).limit(10).all()
    
    # 获取所有菜品信息
    all_dishes = db.session.query(
        Dish.id,
        Dish.name,
        Dish.description,
        Dish.price,
        Category.name.label('category_name')
    ).join(Category).filter(
        Dish.restaurant_id == restaurant_id
    ).all()
    
    # 获取订单总数和总收入
    order_stats = db.session.query(
        func.count(Order.id).label('total_orders'),
        func.sum(Order.total_amount).label('total_revenue')
    ).filter(Order.restaurant_id == restaurant_id).first()
    
    # 获取客户总数
    customer_count = db.session.query(func.count(User.id.distinct())).join(Order).filter(
        Order.restaurant_id == restaurant_id
    ).scalar()
    
    return {
        'top_customers': [{'id': c.id, 'username': c.username, 'total_spent': float(c.total_spent) if c.total_spent else 0} for c in top_customers],
        'top_dishes': [{'id': d.id, 'name': d.name, 'quantity': d.total_quantity, 'orders': d.order_count, 'price': float(d.avg_price) if d.avg_price else 0} for d in top_dishes],
        'all_dishes': [{'id': d.id, 'name': d.name, 'description': d.description, 'price': float(d.price), 'category': d.category_name} for d in all_dishes],
        'order_stats': {
            'total_orders': order_stats.total_orders or 0,
            'total_revenue': float(order_stats.total_revenue) if order_stats.total_revenue else 0
        },
        'customer_count': customer_count or 0
    }


def call_ai_api(prompt, content, restaurant_data=None):
    """调用AI API获取商业顾问回复"""
    GATEWAY_BASE_URL = "https://chat.noc.pku.edu.cn"
    GATEWAY_API_KEY = "GuoWeiCourse_tGv4UT02q7q7"
    MODEL_NAME = "deepseek-v3-250324"
    API_ENDPOINT = f"{GATEWAY_BASE_URL}/v1/chat/completions"

    # 构建包含真实数据的系统提示
    data_info = ""
    if restaurant_data:
        data_info += f"\n餐厅统计数据：\n"
        data_info += f"- 总客户数：{restaurant_data['customer_count']}\n"
        data_info += f"- 总订单数：{restaurant_data['order_stats']['total_orders']}\n"
        data_info += f"- 总收入：¥{restaurant_data['order_stats']['total_revenue']:.2f}\n\n"
        
        data_info += f"消费最多的前10位客户：\n"
        for i, customer in enumerate(restaurant_data['top_customers'], 1):
            data_info += f"{i}. {customer['username']} (ID: {customer['id']}) - 消费总额: ¥{customer['total_spent']:.2f}\n"
        
        data_info += f"\n销量最高的前10道菜品：\n"
        for i, dish in enumerate(restaurant_data['top_dishes'], 1):
            data_info += f"{i}. {dish['name']} (ID: {dish['id']}) - 销量: {dish['quantity']}份, 订单数: {dish['orders']}, 平均价格: ¥{dish['price']:.2f}\n"
        
        data_info += f"\n餐厅所有菜品信息：\n"
        for i, dish in enumerate(restaurant_data['all_dishes'], 1):
            data_info += f"{i}. {dish['name']} (ID: {dish['id']}) - 类别: {dish['category']}, 价格: ¥{dish['price']:.2f}, 描述: {dish['description']}\n"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GATEWAY_API_KEY}"
    }

    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": f"你是一个专业的餐厅商业顾问。你的任务是分析餐厅的经营数据，提供商业建议和回答管理者的问题。以下是当前餐厅的真实数据：\n\n{data_info}\n\n重要规则：\n1. 只能基于提供的真实数据进行分析，不得编造任何未提供的信息\n2. 如果用户询问的数据不在提供的范围内，请明确说明无法提供相关信息\n3. 回答应简洁明了，具有实际操作性\n4. 当提及具体客户或菜品时，必须基于真实数据中的ID和名称"},
            {"role": "user", "content": prompt}
        ],
        "stream": True,
        "temperature": 0.5,  # 降低温度以获得更准确的回答
        "max_tokens": 500
    }

    try:
        response = requests.post(API_ENDPOINT, headers=headers, json=data, stream=True, timeout=300)
        response.raise_for_status()

        ai_reply = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    content_chunk = decoded_line[len('data: '):].strip()
                    if content_chunk == "[DONE]":
                        break
                    try:
                        chunk = json.loads(content_chunk)
                        delta_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta_content:
                            ai_reply += delta_content
                    except json.JSONDecodeError:
                        print(f"JSON decode error: {content_chunk}")

        if not ai_reply.strip():
            raise ValueError("No content received from AI")

        return ai_reply.strip()

    except Exception as e:
        print(f"AI API error: {e}")
        return "商业顾问已收到您的问题: " + content


@bp.route("/chat/<int:restaurant_id>")
@login_required
def chat(restaurant_id):
    """AI商业顾问聊天页面"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 检查用户是否是餐厅的管理者
    if restaurant.manager_id != current_user.id:
        flash("您没有权限访问此餐厅", "danger")
        return redirect(url_for("main.dashboard"))
    
    # 获取最近的对话消息
    messages = ChatMessage.query.filter_by(
        restaurant_id=restaurant_id, 
        user_id=current_user.id, 
        scene="advisor"
    ).order_by(ChatMessage.created_at.desc()).limit(10).all()
    messages.reverse()  # 按时间升序显示
    
    return render_template("advisor/chat.html", restaurant=restaurant, messages=messages)


@bp.route("/send_message/<int:restaurant_id>", methods=["POST"])
@login_required
def send_message(restaurant_id):
    """发送消息给AI商业顾问"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 检查用户是否是餐厅的管理者
    if restaurant.manager_id != current_user.id:
        return jsonify({"status": "error", "msg": "您没有权限访问此餐厅"})
    
    content = request.form["content"]
    if not content.strip():
        return jsonify({"status": "error", "msg": "消息不能为空"})

    # 存储用户消息
    user_msg = ChatMessage(
        restaurant_id=restaurant_id, 
        user_id=current_user.id, 
        role="user", 
        scene="advisor",
        content=content
    )
    db.session.add(user_msg)
    db.session.commit()

    # 获取历史上下文
    history = get_user_history(restaurant_id, current_user.id)

    # 构建系统 prompt
    system_prompt = f"""
你是一个专业的餐厅商业顾问。你的任务是分析餐厅的经营数据，提供商业建议和回答管理者的问题。
餐厅信息：{restaurant.name}
餐厅ID：{restaurant.id}

你可以分析以下数据：
- 用户消费情况
- 菜品销售情况
- 订单统计
- 客户偏好

请根据提供的数据和用户问题给出专业的商业分析和建议。回答要简洁明了，具有实际操作性。
"""

    # 完整 prompt：系统 + 历史 + 新消息
    full_prompt = f"{system_prompt}\n\n对话历史：\n{history}\n\n用户最新消息：{content}\n你的回复："

    # 获取餐厅的真实数据
    restaurant_data = get_restaurant_data(restaurant_id)

    # 调用 AI API
    ai_reply = call_ai_api(full_prompt, content, restaurant_data)

    # 存储 AI 回复
    bot_reply = ChatMessage(
        restaurant_id=restaurant_id, 
        user_id=current_user.id, 
        role="assistant", 
        scene="advisor",
        content=ai_reply
    )
    db.session.add(bot_reply)
    db.session.commit()

    return jsonify({
        "status": "success",
        "user_msg": {
            "id": user_msg.id,
            "content": user_msg.content,
            "timestamp": user_msg.created_at.strftime("%Y-%m-%d %H:%M")
        },
        "bot_msg": {
            "id": bot_reply.id,
            "content": bot_reply.content,
            "timestamp": bot_reply.created_at.strftime("%Y-%m-%d %H:%M")
        }
    })


@bp.route("/load_more/<int:restaurant_id>", methods=["POST"])
@login_required
def load_more(restaurant_id):
    """加载更多对话消息"""
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    
    # 检查用户是否是餐厅的管理者
    if restaurant.manager_id != current_user.id:
        return jsonify({"status": "error", "msg": "您没有权限访问此餐厅"})
    
    offset = int(request.form["offset"])
    limit = 10
    messages = ChatMessage.query.filter_by(
        restaurant_id=restaurant_id, 
        user_id=current_user.id, 
        scene="advisor"
    ).order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit).all()
    messages.reverse()
    data = [
        {"id": m.id, "content": m.content, "role": m.role, "timestamp": m.created_at.strftime("%Y-%m-%d %H:%M")}
        for m in messages
    ]
    return jsonify(data)