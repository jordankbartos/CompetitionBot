"""
Weekly AI news digest — posts a Gemini-generated summary to the AI channel.

Uses google.genai directly (synchronous, no ADK runner) to match the existing
pattern in event_bridge_trigger.py.
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from config import AI_NEWS_WEEKLY_PROMPT, MODEL_NAME
from google.genai import Client
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool
from logging_utils import get_logger
from slack_sdk.errors import SlackApiError

logger = get_logger(__name__)


def post_ai_news_digest(slack_client: Any, google_api_key: str, channel_id: str) -> bool:
    """Generate and post a weekly AI news digest to the given Slack channel.

    Returns True on success, False if generation or posting fails.
    """
    logger.info("post_ai_news_digest: generating AI news digest")

    text = _generate_digest(google_api_key)
    if not text:
        logger.error("post_ai_news_digest: digest generation returned empty text")
        return False

    return _post_message(slack_client, channel_id, text)


def _build_prompt() -> str:
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    return AI_NEWS_WEEKLY_PROMPT.format(
        start_date=week_ago.strftime("%B %d, %Y"),
        end_date=today.strftime("%B %d, %Y"),
    )


def _generate_digest(google_api_key: str) -> Optional[str]:
    try:
        client = Client(api_key=google_api_key)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=_build_prompt(),
            config=GenerateContentConfig(
                tools=[Tool(google_search=GoogleSearch())],
            ),
        )
        if response.candidates:
            candidate = response.candidates[0]
            logger.debug(
                f"_generate_digest: finish_reason={candidate.finish_reason}, "
                f"parts={[type(p).__name__ for p in (candidate.content.parts or [])]}"
            )
        else:
            logger.warning("_generate_digest: response has no candidates")
        return response.text
    except Exception:
        logger.exception("_generate_digest: Gemini generation failed")
        return None


def _post_message(slack_client: Any, channel_id: str, text: str) -> bool:
    try:
        response = slack_client.chat_postMessage(channel=channel_id, text=text)
        if response["ok"]:
            logger.info(f"post_ai_news_digest: posted digest to {channel_id}")
            return True
        logger.error(f"post_ai_news_digest: Slack returned not-ok: {response.get('error')}")
        return False
    except SlackApiError:
        logger.exception("post_ai_news_digest: SlackApiError while posting digest")
        return False
