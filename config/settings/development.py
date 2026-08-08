"""Development settings — SQLite, hardcoded key, DEBUG on. The default module."""

from .base import *  # noqa: F403
from .base import BASE_DIR

# SECURITY WARNING: dev-only key; production reads SECRET_KEY from the environment.
SECRET_KEY = "django-insecure-vto31yznvllwxlu$bmewk$2_)w=h#5$q&7#1(qszww$a5&g-1$"

DEBUG = True

ALLOWED_HOSTS = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
