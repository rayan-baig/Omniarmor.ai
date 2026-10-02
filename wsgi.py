"""Production entry point: gunicorn wsgi:app"""

from omniarmor_app import create_app

app = create_app()
