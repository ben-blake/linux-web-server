import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
DATABASE = os.path.join(BASE_DIR, "nas.db")
NAS_STORAGE = os.environ.get("NAS_STORAGE", "/srv/nas")
NAS_BACKUPS = os.environ.get("NAS_BACKUPS", "/srv/nas-backups")
NAS_QUOTA_GB = float(os.environ.get("NAS_QUOTA_GB", "5"))
