"""
SettlementAgent: handles both fresh-screenshot ingestion and game corrections.

For fresh screenshots it delegates to the SettlementPipeline SequentialAgent
via an AgentTool. For corrections (re-process, fix, delete) it acts directly
using the correction tools.
"""

from typing import Any, Dict, List

from config import MODEL_HEAVY, SETTLEMENT_AGENT_INSTRUCTION
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.agent_tool import AgentTool
from logging_utils import get_logger
from tools.profile import get_user_profile
from tools.settlement_tools import (
    calculate_poker_settlements,
    delete_game_result,
    find_recent_game,
    overwrite_game_result,
    rename_player_in_game_history,
)

from agents.settlement_pipeline import build_settlement_pipeline

logger = get_logger(__name__)


def build_settlement_agent(
    db: Any,
    slack_client: Any,
    slack_token: str,
    google_api_key: str,
    jordan_id: str,
) -> Agent:
    """Constructs and returns the SettlementAgent.

    Args:
        db: PokerDatabase instance.
        slack_client: Slack WebClient instance.
        slack_token: Bot OAuth token.
        google_api_key: Google API key for Gemini.
        jordan_id: Slack ID of Jordan (the admin).

    Returns:
        A configured SettlementAgent LlmAgent.
    """
    model = Gemini(model=MODEL_HEAVY, api_key=google_api_key)

    # The pipeline is wrapped as an AgentTool — the LlmAgent calls it like any other tool
    pipeline = build_settlement_pipeline(
        db=db,
        google_api_key=google_api_key,
        jordan_id=jordan_id,
    )
    pipeline_tool = AgentTool(agent=pipeline)

    # Correction tools — injected dependencies
    def _get_user_profile(slack_id: str) -> dict:
        return get_user_profile(slack_id=slack_id, db=db)

    def _calculate_poker_settlements(player_results: List[Dict[str, Any]]) -> dict:
        return calculate_poker_settlements(player_results=player_results, db=db)

    def _find_recent_game(search_term: str | None = None, limit: int = 10) -> dict:
        return find_recent_game(search_term=search_term, db=db, limit=limit)

    def _overwrite_game_result(
        game_id: str, player_results: List[Dict[str, Any]], uploader_id: str
    ) -> dict:
        return overwrite_game_result(
            game_id=game_id,
            player_results=player_results,
            uploader_id=uploader_id,
            jordan_id=jordan_id,
            db=db,
        )

    def _delete_game_result(game_id: str, uploader_id: str) -> dict:
        return delete_game_result(
            game_id=game_id,
            uploader_id=uploader_id,
            jordan_id=jordan_id,
            db=db,
        )

    def _rename_player_in_game_history(old_name: str, new_name: str, uploader_id: str) -> dict:
        return rename_player_in_game_history(
            old_name=old_name,
            new_name=new_name,
            uploader_id=uploader_id,
            jordan_id=jordan_id,
            db=db,
        )

    # Copy docstrings for ADK schema generation
    _get_user_profile.__doc__ = get_user_profile.__doc__
    _calculate_poker_settlements.__doc__ = calculate_poker_settlements.__doc__
    _find_recent_game.__doc__ = find_recent_game.__doc__
    _overwrite_game_result.__doc__ = overwrite_game_result.__doc__
    _delete_game_result.__doc__ = delete_game_result.__doc__
    _rename_player_in_game_history.__doc__ = rename_player_in_game_history.__doc__

    logger.info("Building SettlementAgent")
    return Agent(
        name="SettlementAgent",
        model=model,
        instruction=SETTLEMENT_AGENT_INSTRUCTION,
        tools=[
            pipeline_tool,
            _get_user_profile,
            _calculate_poker_settlements,
            _find_recent_game,
            _overwrite_game_result,
            _delete_game_result,
            _rename_player_in_game_history,
        ],
    )
