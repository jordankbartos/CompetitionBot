"""
WorkspaceCoordinator: top-level router for all workspace Slack messages.

Routes poker-channel or poker-content messages → PokerCoordinator.
Routes everything else → RoboDuder.
"""

from typing import Any, Optional

from config import MODEL_LIGHT, WORKSPACE_COORDINATOR_INSTRUCTION
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from logging_utils import get_logger

from agents.ai_news_agent import build_ai_news_agent
from agents.coordinator import build_poker_coordinator
from agents.robo_duder import build_robo_duder

logger = get_logger(__name__)


def build_workspace_coordinator(
    db: Any,
    slack_client: Any,
    slack_token: str,
    google_api_key: str,
    jordan_id: str,
    bot_user_id: str,
    action_token: Optional[str] = None,
) -> Agent:
    """Constructs and returns the WorkspaceCoordinator LlmAgent.

    All dependencies are injected — no module-level singletons.
    Signature is identical to build_poker_coordinator for a drop-in swap in slack_bot.py.
    """
    model = Gemini(model=MODEL_LIGHT, api_key=google_api_key)

    poker_coordinator = build_poker_coordinator(
        db=db,
        slack_client=slack_client,
        slack_token=slack_token,
        google_api_key=google_api_key,
        jordan_id=jordan_id,
        bot_user_id=bot_user_id,
        action_token=action_token,
    )
    robo_duder = build_robo_duder(
        slack_client=slack_client,
        slack_token=slack_token,
        google_api_key=google_api_key,
        action_token=action_token,
    )
    ai_news_agent = build_ai_news_agent(google_api_key=google_api_key)

    logger.info(
        "Building WorkspaceCoordinator with sub-agents: PokerCoordinator, RoboDuder, AINewsAgent"
    )
    return Agent(
        name="WorkspaceCoordinator",
        model=model,
        instruction=WORKSPACE_COORDINATOR_INSTRUCTION,
        sub_agents=[poker_coordinator, robo_duder, ai_news_agent],
    )
