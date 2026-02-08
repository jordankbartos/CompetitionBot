"""
Infrastructure for vision-based data extraction from poker screenshots.
Uses Gemini Vision API to parse results.
"""

import json
import logging
from typing import Any, Dict, Optional

import google.generativeai as genai
import requests
from config import MODEL_NAME, VISION_PROMPT

logger = logging.getLogger(__name__)


def download_slack_image(url: str, token: str) -> Optional[bytes]:
    """
    Downloads an image from a Slack private URL.
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.content
        logger.error(f"Failed to download image: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"Network error downloading image: {e}")
    return None


def process_poker_screenshot(image_content: bytes) -> Optional[Dict[str, Any]]:
    """
    Sends an image to the Gemini Vision API and parses the JSON response.

    Returns:
        A dictionary containing extracted player data, or None if extraction fails.
    """
    model = genai.GenerativeModel(MODEL_NAME)

    try:
        response = model.generate_content(
            [VISION_PROMPT, {"mime_type": "image/png", "data": image_content}],
            generation_config={"response_mime_type": "application/json"},
        )
        logger.debug(f"Vision API raw output: {response.text}")

        data = json.loads(response.text)
        if "players" not in data:
            logger.warning(f"Vision output missing 'players' key: {response.text}")

        return data
    except Exception:
        logger.exception("Error during Vision API processing")
        return None
