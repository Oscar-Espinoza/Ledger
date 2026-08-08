"""Import-level tests for config.settings.production — no database needed."""

import importlib
import os
import sys
import unittest
from unittest import mock

from django.core.exceptions import ImproperlyConfigured

MODULE = "config.settings.production"

BASE_ENV = {
    "SECRET_KEY": "test-secret-key",
    "DATABASE_URL": "postgresql://user:pass@db.example.com:5432/ledger",
}


def load_production(**overrides):
    """Import production settings fresh under a controlled environment.

    Pass VAR=None to unset a variable from the base test environment.
    """
    env = {k: v for k, v in {**BASE_ENV, **overrides}.items() if v is not None}
    sys.modules.pop(MODULE, None)
    with mock.patch.dict(os.environ, env, clear=True):
        try:
            return importlib.import_module(MODULE)
        finally:
            sys.modules.pop(MODULE, None)


class ProductionSettingsTests(unittest.TestCase):
    def test_missing_secret_key_raises(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "SECRET_KEY"):
            load_production(SECRET_KEY=None)

    def test_missing_database_url_raises(self):
        with self.assertRaisesRegex(ImproperlyConfigured, "DATABASE_URL"):
            load_production(DATABASE_URL=None)

    def test_debug_defaults_off(self):
        self.assertFalse(load_production().DEBUG)

    def test_debug_enabled_from_env(self):
        self.assertTrue(load_production(DEBUG="true").DEBUG)

    def test_database_url_parsed_with_ssl_and_pooling(self):
        db = load_production().DATABASES["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(db["NAME"], "ledger")
        self.assertEqual(db["CONN_MAX_AGE"], 600)
        self.assertEqual(db["OPTIONS"]["sslmode"], "require")

    def test_render_hostname_joins_allowed_hosts_and_csrf_origins(self):
        settings = load_production(RENDER_EXTERNAL_HOSTNAME="ledger.onrender.com")
        self.assertIn("ledger.onrender.com", settings.ALLOWED_HOSTS)
        self.assertIn("https://ledger.onrender.com", settings.CSRF_TRUSTED_ORIGINS)

    def test_allowed_hosts_env_is_comma_separated(self):
        settings = load_production(ALLOWED_HOSTS="a.example.com,b.example.com")
        self.assertIn("a.example.com", settings.ALLOWED_HOSTS)
        self.assertIn("b.example.com", settings.ALLOWED_HOSTS)

    def test_whitenoise_manifest_storage(self):
        settings = load_production()
        self.assertEqual(
            settings.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_whitenoise_middleware_directly_after_security(self):
        settings = load_production()
        index = settings.MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
        self.assertEqual(
            settings.MIDDLEWARE[index + 1], "whitenoise.middleware.WhiteNoiseMiddleware"
        )

    def test_security_settings(self):
        settings = load_production()
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
        self.assertTrue(settings.SECURE_SSL_REDIRECT)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertGreater(settings.SECURE_HSTS_SECONDS, 0)
