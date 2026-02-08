import os
import requests
import base64
import logging
import json
import google.generativeai as genai
from config import VISION_PROMPT, MODEL_NAME
from utils import get_env

logger = logging.getLogger(__name__)

def download_slack_image(url, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.content
    else:
        logger.error(f"Failed to download image: {response.status_code}")
        return None

def process_poker_screenshot(image_content):
    model = genai.GenerativeModel(MODEL_NAME)
    
    try:
        response = model.generate_content(
            [VISION_PROMPT, {"mime_type": "image/png", "data": image_content}],
            generation_config={"response_mime_type": "application/json"}
        )
        logger.info(f"Vision Raw Output: {response.text}")
        # Validate that we got JSON
        data = json.loads(response.text)
        if 'players' not in data:
            # Fallback or correction
            logger.warning(f"Unexpected vision output: {response.text}")
        return response.text
    except Exception as e:
        logger.exception("Error during Vision API call")
        return None
