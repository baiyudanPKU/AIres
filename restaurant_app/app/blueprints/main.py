from flask import Blueprint, render_template
from flask_login import login_required, current_user

bp = Blueprint("main", __name__)

@bp.get("/dashboard")
@login_required
def dashboard():
    # 这里先做成“二选一”页面
    return render_template("dashboard.html", user=current_user)


