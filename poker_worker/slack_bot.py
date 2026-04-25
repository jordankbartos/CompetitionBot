"""
Main orchestrator for the Poker Bot worker Lambda.
Handles Slack event routing and runs the PokerCoordinator agent graph.
"""

import asyncio
import base64
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agents.workspace_coordinator import build_workspace_coordinator
from config import BOT_USER_ID, JORDAN_ID
from event_bridge_trigger import handle_event_bridge_trigger
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from logging_utils import get_logger
from slack_sdk import WebClient
from tools.slack_tools import is_bot_in_thread

from database import PokerDatabase
from utils import get_env
from vision import download_slack_image

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons — created once per Lambda cold start
# ---------------------------------------------------------------------------
google_api_key: str = get_env("GOOGLE_API_KEY") or ""
slack_token: str = get_env("SLACK_BOT_TOKEN") or ""
client = WebClient(token=slack_token)
db = PokerDatabase()

bot_user_id: str = BOT_USER_ID  # Fallback
try:
    bot_user_id = str(client.auth_test()["user_id"])
    logger.info(f"Authenticated as bot user: {bot_user_id}")
except Exception:
    logger.exception("Failed to authenticate with Slack")


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def img_bytes_to_part(image_data: bytes) -> Part:
    """Converts raw image bytes (or a data-URL) to a Gemini Content Part."""
    if image_data.startswith(b"data:"):
        _, base64_part = image_data.split(b",", 1)
        raw_bytes = base64.b64decode(base64_part)
    elif image_data.startswith(b"\x89PNG") or image_data.startswith(b"\xff\xd8"):
        raw_bytes = image_data
    else:
        try:
            raw_bytes = base64.b64decode(image_data)
        except Exception:
            raw_bytes = image_data

    mime_type = "image/png" if raw_bytes.startswith(b"\x89PNG") else "image/jpeg"
    return Part.from_bytes(data=raw_bytes, mime_type=mime_type)


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


async def _run_agent(agent, prompt: str, image_bytes: Optional[bytes]) -> str:
    """Creates a one-shot session and runs the agent, returning the final text."""
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    session = await session_service.create_session(app_name="WorkspaceBot", user_id="slack_user")
    runner = Runner(
        app_name="WorkspaceBot",
        agent=agent,
        session_service=session_service,
        artifact_service=artifact_service,
    )

    parts = [Part(text=prompt)]
    if image_bytes:
        logger.debug(f"Attaching image part (first 200 bytes: {image_bytes[:200]})")
        parts.append(img_bytes_to_part(image_bytes))

    user_content = Content(role="user", parts=parts)
    final_text = ""
    async for event in runner.run_async(
        user_id="slack_user", session_id=session.id, new_message=user_content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""
    return final_text


# ---------------------------------------------------------------------------
# Core conversation handler
# ---------------------------------------------------------------------------


def handle_agentic_conversation(event_data: Dict[str, Any]) -> None:
    """Runs the WorkspaceCoordinator agent against an incoming Slack event."""
    text = event_data.get("text", "")
    channel = event_data.get("channel", "")
    user_id = event_data.get("user", "")
    ts = event_data.get("ts", "")
    thread_ts = event_data.get("thread_ts")

    logger.info(f"Processing message from {user_id} in {channel}")

    _react(channel, ts, "eyes")

    # Download image if attached
    files = event_data.get("files", [])
    image_bytes: Optional[bytes] = None
    if files:
        file_url = files[0].get("url_private", "")
        image_bytes = download_slack_image(file_url, slack_token)

    # Pull action token for optional workspace search capability
    assistant_thread = event_data.get("assistant_thread", {})
    action_token = event_data.get("action_token") or assistant_thread.get("action_token")

    coordinator = build_workspace_coordinator(
        db=db,
        slack_client=client,
        slack_token=slack_token,
        google_api_key=google_api_key,
        jordan_id=JORDAN_ID,
        bot_user_id=bot_user_id,
        action_token=action_token,
    )

    prompt = _build_prompt(user_id=user_id, text=text, channel=channel, thread_ts=thread_ts)

    try:
        response_text = asyncio.run(_run_agent(coordinator, prompt, image_bytes))
        logger.debug(f"Agent response: {response_text}")
        reply_ts = thread_ts if thread_ts else None
        client.chat_postMessage(channel=channel, text=response_text, thread_ts=reply_ts)
        _react(channel, ts, "eyes", action="remove")
        _react(channel, ts, "heavy_check_mark")
    except Exception:
        logger.exception("Agent conversation failed")
        client.chat_postMessage(
            channel=channel,
            text="Sorry, I ran into an error processing that request.",
            thread_ts=ts,
        )
        _react(channel, ts, "eyes", action="remove")
        _react(channel, ts, "x")


def _react(channel: str, ts: str, emoji: str, action: str = "add") -> None:
    """Add or remove a reaction, swallowing errors so reactions never break the main flow."""
    try:
        if action == "remove":
            client.reactions_remove(channel=channel, timestamp=ts, name=emoji)
        else:
            client.reactions_add(channel=channel, timestamp=ts, name=emoji)
    except Exception:
        logger.warning(f"_react: failed to {action} :{emoji}: on {ts}", exc_info=True)


def _build_prompt(
    user_id: str,
    text: str,
    channel: str,
    thread_ts: Optional[str],
) -> str:
    """Constructs the context-rich prompt for the coordinator."""
    now = datetime.now(tz=timezone.utc).isoformat()
    return (
        f"Context: channel_id={channel}, thread_ts={thread_ts or 'None'}\n"
        f"User <@{user_id}> says: {text}\n"
        f"The current datetime is {now}\n"
    )


# ---------------------------------------------------------------------------
# Lambda entrypoint
# ---------------------------------------------------------------------------


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main AWS Lambda entry point. Routes EventBridge and Slack payloads."""
    logger.debug(f"Received Lambda event: {json.dumps(event)}")

    if event.get("source") == "aws.events":
        return handle_event_bridge_trigger(event, context)

    payload = event.get("payload")
    payload_type = event.get("type")

    if payload_type == "event" and isinstance(payload, dict):
        handle_event(payload)

    return {"statusCode": 200, "body": "OK"}


def handle_event(body: Dict[str, Any]) -> None:
    """Determines whether the bot should respond to a given Slack event."""
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

    if event_type == "app_mention":
        should_respond = True
    elif event_type == "message" and not event_data.get("subtype"):
        # Slack sends both app_mention and message for mentions — ignore the duplicate
        if f"<@{bot_user_id}>" in text:
            return

        thread_ts = event_data.get("thread_ts")
        channel = event_data.get("channel", "")
        if thread_ts and is_bot_in_thread(
            channel_id=channel,
            thread_ts=thread_ts,
            bot_user_id=bot_user_id,
            slack_client=client,
        ):
            logger.info(f"Continuing conversation in thread {thread_ts}")
            should_respond = True

    if should_respond:
        handle_agentic_conversation(event_data)
