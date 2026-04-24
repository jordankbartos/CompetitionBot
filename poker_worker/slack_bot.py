"""
Main orchestrator for the Poker Bot worker.
Handles Slack events, manages agent conversations, and coordinates tools.
"""

import asyncio
import base64
import json
import re
from typing import Any, Dict, Optional

import agent_tools
from config import MODEL_NAME, SYSTEM_PROMPT
from event_bridge_trigger import handle_event_bridge_trigger
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from logging_utils import get_logger
from slack_sdk import WebClient

from database import PokerDatabase
from utils import get_env
from vision import download_slack_image

# Logging configuration
logger = get_logger(__name__)

# Core instances
google_api_key = get_env("GOOGLE_API_KEY")


slack_token = get_env("SLACK_BOT_TOKEN") or ""
client = WebClient(token=slack_token)
db = PokerDatabase()

# Identify bot user ID for message filtering
try:
    bot_user_id = client.auth_test()["user_id"]
    logger.info(f"Authenticated as bot user: {bot_user_id}")
except Exception as e:
    logger.error(f"Failed to authenticate with Slack: {e}")
    bot_user_id = "U07D8V4D145"  # Fallback

# Define the tools available to the AI agent
available_tools = [
    agent_tools.get_user_profile,
    agent_tools.register_player,
    agent_tools.calculate_poker_settlements,
    agent_tools.record_game_result,
    agent_tools.get_leaderboard,
    agent_tools.slack_get_history,
    agent_tools.slack_react,
    agent_tools.get_weekly_poll_results,
]


def img_bytes_to_part(image_data: bytes):
    # 1. Check if this is a Data URL bytes object
    if image_data.startswith(b"data:"):
        print(1)
        header, base64_part = image_data.split(b",", 1)
        raw_bytes = base64.b64decode(base64_part)
    # 2. Check if it's already raw PNG or JPEG binary
    elif image_data.startswith(b"\x89PNG") or image_data.startswith(b"\xff\xd8"):
        print(2)
        raw_bytes = image_data
    # 3. Fallback: Assume it's a raw base64 bytes object without a header
    else:
        print(3)
        try:
            print(4)
            raw_bytes = base64.b64decode(image_data)
        except Exception:
            print(5)
            # If decoding fails, it might just be a raw format we don't recognize
            raw_bytes = image_data

    # Detect mime_type for the API
    m_type = "image/png" if raw_bytes.startswith(b"\x89PNG") else "image/jpeg"

    return Part.from_bytes(data=raw_bytes, mime_type=m_type)


async def get_agent_response(agent, prompt, image_bytes):
    final_text = ""
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="PokerBot", user_id="slack_user")
    runner = Runner(app_name="PokerBot", agent=agent, session_service=session_service)
    # Wrap the prompt into a Content object
    parts = [Part(text=prompt)]
    if image_bytes:
        print(f"{image_bytes[:200]=}")
        image_part = img_bytes_to_part(image_bytes)
        parts.append(image_part)
    user_content = Content(role="user", parts=parts)
    events = runner.run_async(user_id="slack_user", session_id=session.id, new_message=user_content)
    async for event in events:
        if event.is_final_response() and event.content:
            final_text = event.content.parts[0].text
    return final_text


def handle_agentic_conversation(event_data: Dict[str, Any]) -> None:
    """
    Manages a multi-step conversation with the Gemini agent.
    Processes images if present and uses tools to fulfill user requests.
    """
    text = event_data.get("text", "")
    channel = event_data.get("channel", "")
    user_id = event_data.get("user", "")
    ts = event_data.get("ts", "")
    thread_ts = event_data.get("thread_ts")

    logger.info(f"Processing message from {user_id} in {channel}")

    # 1. Image Processing (Vision)
    files = event_data.get("files", [])
    if files:
        file_url = files[0].get("url_private", "")
        image_bytes = download_slack_image(file_url, slack_token)
    else:
        image_bytes = None

    gemini_model = Gemini(
        model=MODEL_NAME,
        api_key=google_api_key,
    )
    agent = Agent(
        name="PokerBot", model=gemini_model, instruction=SYSTEM_PROMPT, tools=available_tools
    )

    prompt = _construct_agent_prompt(
        user_id, text, channel, thread_ts
    )  # , image_bytes)#vision_data)

    try:
        response_text = asyncio.run(get_agent_response(agent, prompt, image_bytes))
        print(f"{response_text=}")
        # Slack replies should usually stay in the same thread if one exists
        reply_ts = thread_ts if thread_ts else None
        client.chat_postMessage(channel=channel, text=response_text, thread_ts=reply_ts)
    except Exception:
        logger.exception("Agent conversation failed")
        client.chat_postMessage(
            channel=channel,
            text="Sorry, I ran into an error processing that request.",
            thread_ts=ts,
        )


def _normalize_vision_results(data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to clean and normalize results from the Vision API."""
    if "players" in data:
        cleaned_players = {}
        for p, val in data["players"].items():
            # Normalize names and convert cents to dollars
            clean_name = re.sub(r"\(.*?\)", "", p).strip()
            # Handle potential string amounts from vision
            amount = float(val) / 100.0
            cleaned_players[clean_name] = cleaned_players.get(clean_name, 0.0) + amount
        data["players"] = cleaned_players
    return data


def _construct_agent_prompt(
    user_id: str,
    text: str,
    channel: str,
    thread_ts: Optional[str],
) -> str:
    """Builds the contextual prompt for the agent."""
    prompt = (
        f"Context: channel_id={channel}, thread_ts={thread_ts or 'None'}\n"
        f"User <@{user_id}> says: {text}\n"
    )
    return prompt


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main entry point for AWS Lambda.
    Routes EventBridge triggers and Slack payloads.
    """
    logger.info(f"Received Lambda event: {json.dumps(event)}")

    # Handle EventBridge (Scheduled tasks)
    if event.get("source") == "aws.events":
        return handle_event_bridge_trigger(event, context)

    # Handle Slack Dispatch
    payload = event.get("payload")
    payload_type = event.get("type")

    if payload_type == "event" and isinstance(payload, dict):
        handle_event(payload)

    return {"statusCode": 200, "body": "OK"}


def handle_event(body: Dict[str, Any]) -> None:
    """Determines if the bot should respond to a given Slack event."""
    if "event" not in body:
        return

    event_data = body["event"]
    event_type = event_data.get("type")
    user_id = event_data.get("user")
    text = event_data.get("text", "")

    # Ignore self and other bots
    if user_id == bot_user_id or event_data.get("subtype") == "bot_message":
        return

    should_respond = False

    # Always respond to direct mentions
    if event_type == "app_mention":
        should_respond = True

    # Respond to messages in threads where the bot is already participating
    elif event_type == "message" and not event_data.get("subtype"):
        # Slack sends both app_mention and message for mentions; ignore the duplicate
        if f"<@{bot_user_id}>" in text:
            return

        thread_ts = event_data.get("thread_ts")
        channel = event_data.get("channel", "")
        if thread_ts and agent_tools.is_bot_in_thread(channel, thread_ts):
            logger.info(f"Continuing conversation in thread {thread_ts}")
            should_respond = True

    if should_respond:
        handle_agentic_conversation(event_data)
