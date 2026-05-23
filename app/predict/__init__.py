from flask import Blueprint

predict_bp = Blueprint("predict", __name__)

from app.predict import routes  # noqa: E402, F401
