# Точка входа для ревьюера: uvicorn recommendations_service:app --port 8000
from app.recommendations_service import app

__all__ = ["app"]
