"""
RoboDuder: general-purpose Slack workspace agent.

Handles channel history, reactions, file viewing, and optional workspace search.
No database dependency — all interactions are Slack-API-only.
"""

from typing import Any, Optional

from config import MODEL_LIGHT, ROBO_DUDER_INSTRUCTION
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.load_artifacts_tool import LoadArtifactsTool
from logging_utils import get_logger
from tools.slack_tools import (
    create_slack_search_tool,
    get_message_files,
    save_slack_file_as_artifact,
    slack_react,
    slack_recent_channel_history,
)

logger = get_logger(__name__)


def build_robo_duder(
    slack_client: Any,
    slack_token: str,
    google_api_key: str,
    action_token: Optional[str] = None,
) -> Agent:
    """Constructs and returns the RoboDuder general-purpose Slack agent."""
    model = Gemini(model=MODEL_LIGHT, api_key=google_api_key)

    def _slack_recent_channel_history(
        channel_id: str, limit: int = 20, thread_ts: str | None = None
    ) -> dict:
        return slack_recent_channel_history(
            channel_id=channel_id, slack_client=slack_client, limit=limit, thread_ts=thread_ts
        )

    def _slack_react(channel_id: str, timestamp: str, emoji: str, action: str = "add") -> dict:
        return slack_react(
            channel_id=channel_id,
            timestamp=timestamp,
            emoji=emoji,
            slack_client=slack_client,
            action=action,
        )

    async def _save_slack_file_as_artifact(file_id: str, tool_context: Any) -> dict:
        return await save_slack_file_as_artifact(
            file_id=file_id,
            tool_context=tool_context,
            slack_client=slack_client,
            slack_token=slack_token,
        )

    def _get_message_files(channel_id: str, message_ts: str) -> dict:
        return get_message_files(
            channel_id=channel_id, message_ts=message_ts, slack_client=slack_client
        )

    _slack_recent_channel_history.__doc__ = slack_recent_channel_history.__doc__
    _slack_react.__doc__ = slack_react.__doc__
    _save_slack_file_as_artifact.__doc__ = save_slack_file_as_artifact.__doc__
    _get_message_files.__doc__ = get_message_files.__doc__

    tools: list = [
        _slack_recent_channel_history,
        _slack_react,
        _save_slack_file_as_artifact,
        _get_message_files,
        LoadArtifactsTool(),
    ]

    if action_token:
        tools.append(create_slack_search_tool(action_token=action_token, slack_client=slack_client))
        logger.info("RoboDuder: injected slack_search tool")

    logger.info("Building RoboDuder")
    return Agent(
        name="RoboDuder",
        model=model,
        instruction=ROBO_DUDER_INSTRUCTION,
        tools=tools,
    )
