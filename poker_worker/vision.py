"""
Infrastructure helpers for vision-related tasks.

The heavy Gemini vision processing has been moved into the SettlementPipeline's
VisionStep agent (poker_worker/agents/settlement_pipeline.py).

This module retains only the Slack image download helper used by slack_bot.py.
"""

from typing import Optional

import requests
from logging_utils import get_logger

logger = get_logger(__name__)


def download_slack_image(url: str, token: str) -> Optional[bytes]:
    """Downloads an image from a Slack private URL.

    Args:
        url: The private Slack URL of the image.
        token: The bot OAuth token for authenticated download.

    Returns:
        Raw image bytes, or None if the download fails.
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.content
        logger.error(f"Failed to download image: status {response.status_code}")
    except requests.RequestException:
        logger.exception("Network error downloading image")
    return None
