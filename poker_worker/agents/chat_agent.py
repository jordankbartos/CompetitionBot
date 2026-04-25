"""
ChatAgent: catch-all sub-agent handling registration, poll results, and general conversation.
"""

from typing import Any, Optional

from config import CHAT_AGENT_INSTRUCTION, MODEL_LIGHT
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.load_artifacts_tool import LoadArtifactsTool
from logging_utils import get_logger
from tools.poll import get_weekly_poll_results
from tools.profile import get_user_profile, register_player_venmo
from tools.slack_tools import (
    create_slack_search_tool,
    get_message_files,
    save_slack_file_as_artifact,
    slack_react,
    slack_recent_channel_history,
)

logger = get_logger(__name__)


def build_chat_agent(
    db: Any,
    slack_client: Any,
    slack_token: str,
    google_api_key: str,
    jordan_id: str,
    action_token: Optional[str] = None,
) -> Agent:
    """Constructs and returns the ChatAgent.

    Args:
        db: PokerDatabase instance.
        slack_client: Slack WebClient instance.
        slack_token: Bot OAuth token (for file downloads).
        google_api_key: Google API key for Gemini.
        jordan_id: Slack ID of Jordan (the admin).
        action_token: Optional Slack action token enabling workspace search.

    Returns:
        A configured ChatAgent LlmAgent.
    """
    model = Gemini(model=MODEL_LIGHT, api_key=google_api_key)

    def _get_user_profile(slack_id: str) -> dict:
        return get_user_profile(slack_id=slack_id, db=db)

    def _register_player_venmo(slack_id: str, poker_name: str, venmo_handle: str) -> dict:
        return register_player_venmo(
            slack_id=slack_id, poker_name=poker_name, venmo_handle=venmo_handle, db=db
        )

    def _get_weekly_poll_results() -> dict:
        return get_weekly_poll_results(db=db, slack_client=slack_client)

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

    async def _save_slack_file_as_artifact(file_id: str, tool_context) -> dict:
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

    # Copy docstrings so ADK can build the tool schema
    _get_user_profile.__doc__ = get_user_profile.__doc__
    _register_player_venmo.__doc__ = register_player_venmo.__doc__
    _get_weekly_poll_results.__doc__ = get_weekly_poll_results.__doc__
    _slack_recent_channel_history.__doc__ = slack_recent_channel_history.__doc__
    _slack_react.__doc__ = slack_react.__doc__
    _save_slack_file_as_artifact.__doc__ = save_slack_file_as_artifact.__doc__
    _get_message_files.__doc__ = get_message_files.__doc__

    tools = [
        _get_user_profile,
        _register_player_venmo,
        _get_weekly_poll_results,
        _slack_recent_channel_history,
        _slack_react,
        _save_slack_file_as_artifact,
        _get_message_files,
        LoadArtifactsTool(),
    ]

    if action_token:
        tools.append(create_slack_search_tool(action_token=action_token, slack_client=slack_client))
        logger.info("ChatAgent: injected slack_search tool with action_token")

    logger.info("Building ChatAgent")
    return Agent(
        name="ChatAgent",
        model=model,
        instruction=CHAT_AGENT_INSTRUCTION,
        tools=tools,
    )
