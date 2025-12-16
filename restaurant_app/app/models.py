from datetime import datetime
from flask_login import UserMixin
from . import db, login_manager

# -------------------------
# 用户
# -------------------------
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    avatar_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # 关系
    restaurants = db.relationship("Restaurant", back_populates="manager", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")
    chats = db.relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------------
# 餐厅
# -------------------------
class Restaurant(db.Model):
    __tablename__ = "restaurants"
    id = db.Column(db.Integer, primary_key=True)

    # 餐厅不可重名（全局唯一）
    name = db.Column(db.String(80), unique=True, nullable=False)

    # Logo 存相对路径：例如 uploads/restaurants/xxx.png
    logo_path = db.Column(db.String(255), nullable=True)

    # 管理者（用户）
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # 关系
    manager = db.relationship("User", back_populates="restaurants")
    categories = db.relationship("Category", back_populates="restaurant", cascade="all, delete-orphan")
    dishes = db.relationship("Dish", back_populates="restaurant", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="restaurant", cascade="all, delete-orphan")
    blacklists = db.relationship("Blacklist", back_populates="restaurant", cascade="all, delete-orphan")
    chats = db.relationship("ChatMessage", back_populates="restaurant", cascade="all, delete-orphan")


# -------------------------
# 分类（每个餐厅固定四个分类：菜品/主食/甜品/饮品）
# -------------------------
class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)

    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    # 固定四类：菜品 / 主食 / 甜品 / 饮品
    name = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # 同一家餐厅内分类名不能重复
    __table_args__ = (
        db.UniqueConstraint("restaurant_id", "name", name="uq_category_restaurant_name"),
    )

    restaurant = db.relationship("Restaurant", back_populates="categories")
    dishes = db.relationship("Dish", back_populates="category", cascade="all, delete-orphan")


# -------------------------
# 菜品
# -------------------------
class Dish(db.Model):
    __tablename__ = "dishes"
    id = db.Column(db.Integer, primary_key=True)

    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    name = db.Column(db.String(80), nullable=False)
    image_path = db.Column(db.String(255), nullable=True)

    description = db.Column(db.String(500), nullable=False)  # <=500字
    price = db.Column(db.Numeric(10, 2), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("restaurant_id", "name", name="uq_dish_restaurant_name"),
    )

    restaurant = db.relationship("Restaurant", back_populates="dishes")
    category = db.relationship("Category", back_populates="dishes")

    # 重点：删除菜品时，相关 OrderItem 必须删除
    order_items = db.relationship(
        "OrderItem",
        back_populates="dish",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )





# -------------------------
# 订单（一次“付款”生成一条）
# -------------------------
class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="orders")
    restaurant = db.relationship("Restaurant", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


# -------------------------
# 订单项（订单里的每道菜、份数、单价）
# -------------------------
class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey("dishes.id", ondelete="CASCADE"), nullable=False)

    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    dish = db.relationship("Dish", back_populates="order_items")


# -------------------------
# 黑名单（某餐厅拉黑某用户）
# -------------------------
class Blacklist(db.Model):
    __tablename__ = "blacklists"
    id = db.Column(db.Integer, primary_key=True)

    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("restaurant_id", "user_id", name="uq_blacklist_restaurant_user"),
    )

    restaurant = db.relationship("Restaurant", back_populates="blacklists")
    user = db.relationship("User")


# -------------------------
# 聊天记录（菜品询问 + 顾问都用它）
# role: "user" / "assistant"
# scene: "dish" / "advisor"
# dish_id 可空（顾问对话不绑定菜品）
# -------------------------
class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)

    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    dish_id = db.Column(db.Integer, db.ForeignKey("dishes.id"), nullable=True)

    role = db.Column(db.String(20), nullable=False)   # user / assistant
    scene = db.Column(db.String(20), nullable=False)  # dish / advisor
    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    restaurant = db.relationship("Restaurant", back_populates="chats")
    user = db.relationship("User", back_populates="chats")

