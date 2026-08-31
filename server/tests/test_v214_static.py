from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version214StaticTests(unittest.TestCase):
    def test_webclient_contains_theme_and_wake_controls(self):
        html = (ROOT / "server/web/templates/connect.html").read_text(encoding="utf-8")
        app_js = (ROOT / "server/web/static/js/app.js").read_text(encoding="utf-8")
        self.assertIn('id="settingsTheme"', html)
        self.assertIn('id="settingsWakeLock"', html)
        self.assertIn('navigator.wakeLock.request("screen")', app_js)
        self.assertIn('prefers-color-scheme: dark', app_js)

    def test_service_worker_cache_is_versioned_and_purges_stale_caches(self):
        """Niet het nummer vastpinnen, maar het mechanisme.

        De oude test eiste een specifieke versie en brak dus bij elke
        legitieme ophoging. Wat telt is dat er een versie is en dat oude
        caches worden opgeruimd, anders blijven clients op verouderde
        bestanden hangen.
        """
        source = (ROOT / "server/web/static/js/service-worker.js").read_text(encoding="utf-8")
        match = re.search(r'const CACHE = "eventhub-live-v(\d+)"', source)
        self.assertIsNotNone(match, "service worker heeft geen genummerde cacheversie")
        self.assertGreaterEqual(int(match.group(1)), 18, "cacheversie mag niet teruglopen")
        self.assertIn('key.startsWith("eventhub-live-")', source)
        self.assertIn("caches.delete(key)", source)

    def test_profile_schema_contains_signature(self):
        from emt_models import DEFAULT_PROFILE
        self.assertEqual(DEFAULT_PROFILE["signature_organization"], "Ministerie van Defensie")
        self.assertIn("signature_rank", DEFAULT_PROFILE)
        self.assertIn("signature_first_name", DEFAULT_PROFILE)
        self.assertIn("signature_department", DEFAULT_PROFILE)


if __name__ == "__main__":
    unittest.main()
