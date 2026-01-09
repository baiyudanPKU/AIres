from app import create_app, db
from app.models import User, Restaurant, Category, Dish, Order, OrderItem, Blacklist, ChatMessage
import os

app = create_app()

# Initialize database if it doesn't exist
with app.app_context():
    # Create all tables
    db.create_all()
    print("Database tables created successfully")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
