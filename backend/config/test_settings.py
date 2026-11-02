import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("SECURE_SSL_REDIRECT", "false")

from config.settings import *  # noqa: E402, F403
