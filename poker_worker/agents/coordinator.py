"""
PokerCoordinator: the root LlmAgent that routes incoming requests
to the appropriate specialist sub-agent.

Designed to be instantiated per-request (stateless construction) so it can
eventually be slotted into a parent workspace agent's sub_agents list with
no internal changes.
"""

from typing import Any

from config import COORDINATOR_INSTRUCTION, MODEL_LIGHT
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from logging_utils import get_logger

from agents.chat_agent import build_chat_agent
from agents.leaderboard_agent import build_leaderboard_agent
from agents.settlement_agent import build_settlement_agent

logger = get_logger(__name__)


def build_poker_coordinator(
    db: Any,
    slack_client: Any,
    slack_token: str,
    google_api_key: str,
    jordan_id: str,
    bot_user_id: str,
    action_token: str | None = None,
) -> Agent:
    """Constructs and returns the PokerCoordinator LlmAgent.

    All dependencies are injected — no module-level singletons.

    Args:
        db: PokerDatabase instance.
        slack_client: Slack WebClient instance.
        slack_token: Bot OAuth token (needed for file downloads).
        google_api_key: Google API key for Gemini.
        jordan_id: Slack ID of Jordan (the admin).
        bot_user_id: The bot's own Slack user ID (used by thread-check logic upstream).
        action_token: Optional Slack action token enabling workspace search.

    Returns:
        A fully configured PokerCoordinator LlmAgent.
    """
    model = Gemini(model=MODEL_LIGHT, api_key=google_api_key)

    settlement_agent = build_settlement_agent(
        db=db,
        slack_client=slack_client,
        slack_token=slack_token,
        google_api_key=google_api_key,
        jordan_id=jordan_id,
    )
    leaderboard_agent = build_leaderboard_agent(
        db=db,
        google_api_key=google_api_key,
    )
    chat_agent = build_chat_agent(
        db=db,
        slack_client=slack_client,
        slack_token=slack_token,
        google_api_key=google_api_key,
        jordan_id=jordan_id,
        action_token=action_token,
    )

    logger.info("Building PokerCoordinator with sub-agents: Settlement, Leaderboard, Chat")
    return Agent(
        name="PokerCoordinator",
        model=model,
        instruction=COORDINATOR_INSTRUCTION,
        sub_agents=[settlement_agent, leaderboard_agent, chat_agent],
    )
