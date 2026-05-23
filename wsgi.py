"""WSGI entry point for Gunicorn.

Usage:
    gunicorn --workers 1 --bind 0.0.0.0:8000 wsgi:app
"""
from app import create_app

app = create_app()
