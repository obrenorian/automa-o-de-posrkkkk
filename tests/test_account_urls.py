from __future__ import annotations

import unittest

from app.automation.account_urls import build_reels_composer_url


class AccountUrlTests(unittest.TestCase):
    def test_builds_stable_url_without_redirect_session(self) -> None:
        url = build_reels_composer_url(
            {
                "instagram_name": "@achadinhos01",
                "business_id": "123456789012345",
                "page_id": "234567890123456",
                "asset_id": "234567890123456",
            }
        )

        self.assertIn("business_id=123456789012345", url)
        self.assertIn("page_id=234567890123456", url)
        self.assertNotIn("redirect_session_id", url)


if __name__ == "__main__":
    unittest.main()
