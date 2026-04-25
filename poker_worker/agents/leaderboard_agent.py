"""
LeaderboardAgent: thin read-only sub-agent for leaderboard and player stat queries.
"""

from typing import Any

from config import LEADERBOARD_AGENT_INSTRUCTION, MODEL_LIGHT
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from logging_utils import get_logger
from tools.leaderboard import get_poker_leaderboard
from tools.profile import get_user_profile

logger = get_logger(__name__)


def build_leaderboard_agent(db: Any, google_api_key: str) -> Agent:
    """Constructs and returns the LeaderboardAgent.

    Args:
        db: PokerDatabase instance.
        google_api_key: Google API key for Gemini.

    Returns:
        A configured LeaderboardAgent LlmAgent.
    """
    model = Gemini(model=MODEL_LIGHT, api_key=google_api_key)

    def _get_poker_leaderboard() -> dict:
        return get_poker_leaderboard(db=db)

    def _get_user_profile(slack_id: str) -> dict:
        return get_user_profile(slack_id=slack_id, db=db)

    _get_poker_leaderboard.__doc__ = get_poker_leaderboard.__doc__
    _get_user_profile.__doc__ = get_user_profile.__doc__

    logger.info("Building LeaderboardAgent")
    return Agent(
        name="LeaderboardAgent",
        model=model,
        instruction=LEADERBOARD_AGENT_INSTRUCTION,
        tools=[_get_poker_leaderboard, _get_user_profile],
    )
