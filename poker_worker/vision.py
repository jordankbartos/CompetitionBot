"""
Infrastructure for vision-based data extraction from poker screenshots.
Uses Gemini Vision API to parse results.
"""

import json
from typing import Any, Dict, Optional

import requests
from config import MODEL_NAME, VISION_PROMPT
from google import genai
from google.genai.types import Content, Part
from logging_utils import get_logger

from utils import get_env

google_api_key = get_env("GOOGLE_API_KEY")

logger = get_logger(__name__)


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
    print("VISION TOOL")
    client = genai.Client(vertexai=False, api_key=google_api_key)
    system_prompt = Content(role="system", parts=[Part(text=VISION_PROMPT)])
    image_part = Part.from_bytes(data=image_content, mime_type="image/png")
    user_prompt = Content(role="user", parts=[image_part])

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[system_prompt, user_prompt],
            generation_config={"response_mime_type": "application/json"},
        )
        # response = model.generate_content(
        #    [VISION_PROMPT, {"mime_type": "image/png", "data": image_content}],
        #    generation_config={"response_mime_type": "application/json"},
        # )
        logger.debug(f"Vision API raw output: {response.text}")

        data = json.loads(response.text)
        if "players" not in data:
            logger.warning(f"Vision output missing 'players' key: {response.text}")

        return data
    except Exception:
        logger.exception("Error during Vision API processing")
        return None
