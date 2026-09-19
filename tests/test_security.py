from __future__ import annotations

import os
from unittest.mock import patch
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from security import validate_local_browser_request  # noqa: E402


class LocalApiSecurityTests(unittest.TestCase):
    def test_hotspot_host_requires_lan_and_preserves_origin_checks(self) -> None:
        with patch.dict(os.environ, {"KEIVOTOS_HOTSPOT_HOST": "192.168.137.1"}):
            for host, origin, lan, fetch, expected in [
                ("192.168.137.1", None, "172.19.54.140", None, None),
                ("192.168.137.1", "http://192.168.137.1:53325", "172.19.54.140", "same-origin", None),
                ("192.168.137.1", None, None, None, 400),
                ("192.168.137.2", None, "172.19.54.140", None, 400),
                ("192.168.137.1", "http://attacker.example", "172.19.54.140", None, 403),
                ("192.168.137.1", "http://192.168.137.1:80", "172.19.54.140", None, 403),
                ("192.168.137.1", None, "172.19.54.140", "cross-site", 403),
            ]:
                with self.subTest(host=host, origin=origin, lan=lan, fetch=fetch):
                    result = validate_local_browser_request(
                        host_header=host + ":53325", scheme="http",
                        origin_header=origin, lan_host=lan, fetch_site_header=fetch,
                    )
                    self.assertEqual(result[0] if result else None, expected)

    def test_invalid_hotspot_configuration_does_not_allow_host(self) -> None:
        for host in ("*", "attacker.example", "8.8.8.8", "0.0.0.0", "224.0.0.1"):
            with self.subTest(host=host), patch.dict(os.environ, {"KEIVOTOS_HOTSPOT_HOST": host}):
                result = validate_local_browser_request(
                    host_header=host + ":53325", scheme="http", origin_header=None,
                    lan_host="172.19.54.140",
                )
                self.assertEqual(result[0] if result else None, 400)

    def test_same_origin_loopback_browser_request_is_allowed(self) -> None:
        self.assertIsNone(validate_local_browser_request(
            host_header="localhost:54325",
            scheme="http",
            origin_header="http://localhost:54325",
        ))

    def test_loopback_navigation_without_origin_is_allowed(self) -> None:
        self.assertIsNone(validate_local_browser_request(
            host_header="localhost:54325",
            scheme="http",
            origin_header=None,
        ))

    def test_cross_origin_browser_request_is_rejected(self) -> None:
        rejection = validate_local_browser_request(
            host_header="localhost:54325",
            scheme="http",
            origin_header="https://example.com",
        )
        self.assertEqual(rejection[0] if rejection else None, 403)

    def test_non_loopback_host_is_rejected(self) -> None:
        rejection = validate_local_browser_request(
            host_header="attacker.example:54325",
            scheme="http",
            origin_header=None,
        )
        self.assertEqual(rejection[0] if rejection else None, 400)

    def test_same_origin_lan_browser_request_is_allowed_when_enabled(self) -> None:
        self.assertIsNone(validate_local_browser_request(
            host_header="192.168.1.25:54325",
            scheme="http",
            origin_header="http://192.168.1.25:54325",
            lan_host="192.168.1.25",
        ))

    def test_other_lan_host_is_rejected_when_one_address_is_enabled(self) -> None:
        rejection = validate_local_browser_request(
            host_header="192.168.1.26:54325",
            scheme="http",
            origin_header=None,
            lan_host="192.168.1.25",
        )
        self.assertEqual(rejection[0] if rejection else None, 400)

    def test_lan_cross_origin_browser_request_is_rejected(self) -> None:
        rejection = validate_local_browser_request(
            host_header="192.168.1.25:54325",
            scheme="http",
            origin_header="http://192.168.1.26:54325",
            lan_host="192.168.1.25",
        )
        self.assertEqual(rejection[0] if rejection else None, 403)

    def test_cross_site_subresource_without_origin_is_rejected(self) -> None:
        rejection = validate_local_browser_request(
            host_header="localhost:54325",
            scheme="http",
            origin_header=None,
            fetch_site_header="cross-site",
        )
        self.assertEqual(rejection[0] if rejection else None, 403)


if __name__ == "__main__":
    unittest.main()
