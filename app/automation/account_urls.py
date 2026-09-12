from __future__ import annotations

from urllib.parse import urlencode


def build_reels_composer_url(account: dict[str, str]) -> str:
    """Monta a URL estavel sem reutilizar redirect_session_id temporario."""
    required = ("business_id", "page_id", "asset_id")
    missing = [field for field in required if not account.get(field)]
    if missing:
        raise ValueError(
            "identificadores ausentes na conta: " + ", ".join(missing)
        )
    params = {
        "global_scope_id": account["business_id"],
        "business_id": account["business_id"],
        "page_id": account["page_id"],
        "asset_id": account["asset_id"],
    }
    return "https://business.facebook.com/latest/reels_composer/?" + urlencode(params)
