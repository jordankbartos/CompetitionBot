"""
Settlement SequentialAgent pipeline.

Handles the 'fresh screenshot' happy path in five strict steps:
  1. VisionStep       — parse screenshot -> raw player amounts + game_id
  2. NameResolverStep — fuzzy-match raw names to registered poker names
  3. CalculateStep    — deterministic debt calculation (no LLM)
  4. PersistStep      — save to DB, handle dup/Jordan-auth logic
  5. FormatStep       — produce final Slack-formatted message

This pipeline is exposed as an AgentTool to the SettlementAgent, so the
SettlementAgent can call it for the standard case while still retaining
the ability to handle corrections and edge cases directly.
"""

from typing import Any, Dict, List

from config import (
    FORMAT_STEP_INSTRUCTION,
    MODEL_HEAVY,
    MODEL_LIGHT,
    NAME_RESOLVER_STEP_INSTRUCTION,
    PERSIST_STEP_INSTRUCTION,
    VISION_STEP_INSTRUCTION,
)
from google.adk.agents import Agent, SequentialAgent
from google.adk.models.google_llm import Gemini
from logging_utils import get_logger
from tools.profile import get_user_profile
from tools.settlement_tools import calculate_poker_settlements, record_game_result

logger = get_logger(__name__)


def build_settlement_pipeline(
    db: Any,
    google_api_key: str,
    jordan_id: str,
) -> SequentialAgent:
    """Constructs the five-step SequentialAgent for processing fresh screenshots.

    Args:
        db: PokerDatabase instance.
        google_api_key: Google API key for Gemini.
        jordan_id: Slack ID of the admin (Jordan).

    Returns:
        A SequentialAgent that processes one game screenshot end-to-end.
    """
    model_heavy = Gemini(model=MODEL_HEAVY, api_key=google_api_key)
    model_light = Gemini(model=MODEL_LIGHT, api_key=google_api_key)

    # ------------------------------------------------------------------
    # Step 1: Vision — parse the screenshot
    # ------------------------------------------------------------------
    vision_step = Agent(
        name="VisionStep",
        model=model_heavy,
        instruction=VISION_STEP_INSTRUCTION,
        tools=[],
        output_key="vision_output",
    )

    # ------------------------------------------------------------------
    # Step 2: Name Resolver — match raw names to registered players
    # ------------------------------------------------------------------
    def _get_user_profile(slack_id: str) -> dict:
        return get_user_profile(slack_id=slack_id, db=db)

    _get_user_profile.__doc__ = get_user_profile.__doc__

    name_resolver_step = Agent(
        name="NameResolverStep",
        model=model_light,
        instruction=NAME_RESOLVER_STEP_INSTRUCTION,
        tools=[_get_user_profile],
        output_key="resolved_players",
    )

    # ------------------------------------------------------------------
    # Step 3: Calculate — deterministic, uses calculate_poker_settlements
    # No LLM reasoning needed; we wrap the tool in a minimal agent.
    # ------------------------------------------------------------------
    def _calculate_poker_settlements(player_results: List[Dict[str, Any]]) -> dict:
        return calculate_poker_settlements(player_results=player_results, db=db)

    _calculate_poker_settlements.__doc__ = calculate_poker_settlements.__doc__

    # The instruction tells the agent exactly what to do — one tool call, output to state.
    calculate_step = Agent(
        name="CalculateStep",
        model=model_light,
        instruction=(
            "You are the calculation step. Read the resolved_players from context, "
            "call calculate_poker_settlements with the player data as a list of "
            '{"name": ..., "amount": ...} dicts, and write the result to state key \'settlements\'.'
        ),
        tools=[_calculate_poker_settlements],
        output_key="settlements",
    )

    # ------------------------------------------------------------------
    # Step 4: Persist — save to DB, handle duplicates / Jordan auth
    # ------------------------------------------------------------------
    def _record_game_result(
        player_results: List[Dict[str, Any]],
        uploader_id: str,
        game_id: str | None = None,
        force_overwrite: bool = False,
    ) -> dict:
        return record_game_result(
            player_results=player_results,
            uploader_id=uploader_id,
            jordan_id=jordan_id,
            db=db,
            game_id=game_id,
            force_overwrite=force_overwrite,
        )

    _record_game_result.__doc__ = record_game_result.__doc__

    persist_step = Agent(
        name="PersistStep",
        model=model_light,
        instruction=PERSIST_STEP_INSTRUCTION,
        tools=[_record_game_result],
        output_key="persistence_result",
    )

    # ------------------------------------------------------------------
    # Step 5: Format — produce the final Slack message
    # ------------------------------------------------------------------
    format_step = Agent(
        name="FormatStep",
        model=model_light,
        instruction=FORMAT_STEP_INSTRUCTION,
        tools=[],
        output_key="final_message",
    )

    logger.info("Building SettlementPipeline (SequentialAgent)")
    return SequentialAgent(
        name="SettlementPipeline",
        sub_agents=[vision_step, name_resolver_step, calculate_step, persist_step, format_step],
    )
