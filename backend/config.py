"""
Meldpunt Ambtenaren — Configuratie
"""
import os
import secrets

class Config:
    # Flask
    SECRET_KEY = os.environ.get('MELDPUNT_SECRET_KEY') or secrets.token_hex(32)

    # PostgreSQL
    DB_HOST = os.environ.get('MELDPUNT_DB_HOST', 'localhost')
    DB_PORT = os.environ.get('MELDPUNT_DB_PORT', '5432')
    DB_NAME = os.environ.get('MELDPUNT_DB_NAME', 'meldpunt')
    DB_USER = os.environ.get('MELDPUNT_DB_USER', 'meldpunt')
    DB_PASS = os.environ.get('MELDPUNT_DB_PASS', '')
    # Gebruik SQLite als DATABASE_URL niet gezet is (lokaal testen)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}' \
        if os.environ.get('DATABASE_URL') or DB_PASS else \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'meldpunt.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('MELDPUNT_HTTPS', 'false').lower() == 'true'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 uur

    # Rate limiting
    RATELIMIT_DEFAULT = "60/minute"
    RATELIMIT_SUBMIT = "5/hour"  # max 5 meldingen per uur per IP

    # Uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max

    # Admin — eerste admin wordt aangemaakt via migrate.py
    ADMIN_DEFAULT_USER = os.environ.get('MELDPUNT_ADMIN_USER', 'admin')
    ADMIN_DEFAULT_PASS = os.environ.get('MELDPUNT_ADMIN_PASS', '')  # MOET gezet worden bij deploy
