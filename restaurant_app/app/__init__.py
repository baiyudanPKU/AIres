import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from .config import Config
from dotenv import load_dotenv

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    load_dotenv()
    from .config import Config

    app = Flask(__name__)
    app.config.from_object(Config)

    # ✅ 再兜底一层（强烈建议加）
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    from . import models  # ✅ 确保模型被导入，让 migrate 能发现

    login_manager.login_view = "auth.login"

    # from .blueprints.auth import bp as main_bp
    # app.register_blueprint(main_bp)

    from .blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .blueprints.main import bp as main_bp
    app.register_blueprint(main_bp)

    from .blueprints.manage import bp as manage_bp
    app.register_blueprint(manage_bp)


    @app.get("/")
    def index():
        return "OK: App Factory Running"

    return app

