import os
import requests
import base64
import logging
from openai import OpenAI
from config import VISION_PROMPT

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
    client = OpenAI()
    
    # Encode image to base64
    base64_image = base64.b64encode(image_content).decode('utf-8')
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception("Error during Vision API call")
        return None
