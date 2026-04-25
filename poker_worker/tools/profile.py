"""
Tools for player profile management: lookup and registration.
"""

from typing import Any, Dict

from logging_utils import get_logger

logger = get_logger(__name__)


def get_user_profile(slack_id: str, db: Any) -> Dict[str, Any]:
    """Retrieves the poker name and Venmo handle for a given Slack user ID.

    Args:
        slack_id: The Slack user ID (e.g., 'U12345').
        db: PokerDatabase instance.

    Returns:
        Dict[str, Any] with keys:
          - "status": "success" or "failure"
          - "data": dict with 'poker_name' and 'venmo_handle' if found, else None.
          - "error_message": error details or None.
    """
    logger.info(f"Tool get_user_profile invoked with slack_id: {slack_id}")
    try:
        profile = db.get_user_by_slack_id(slack_id)
        if profile:
            logger.info(f"Tool get_user_profile: found profile for {slack_id}")
            return {
                "status": "success",
                "data": {
                    "poker_name": profile.get("poker_name", ""),
                    "venmo_handle": profile.get("venmo_handle", ""),
                },
                "error_message": None,
            }
        logger.info(f"Tool get_user_profile: no profile for {slack_id}")
        return {
            "status": "success",
            "data": None,
            "error_message": "User profile not found.",
        }
    except Exception as e:
        logger.exception("Error in get_user_profile")
        return {"status": "failure", "data": None, "error_message": str(e)}


def register_player_venmo(
    slack_id: str, poker_name: str, venmo_handle: str, db: Any
) -> Dict[str, Any]:
    """Registers a new player with their poker name and Venmo handle.

    Args:
        slack_id: The Slack user ID.
        poker_name: Their display name in poker games.
        venmo_handle: Their Venmo handle (with or without '@').
        db: PokerDatabase instance.

    Returns:
        Dict[str, Any] with keys:
          - "status": "success" or "failure"
          - "data": confirmation string or None.
          - "error_message": error details or None.
    """
    logger.info(f"Tool register_player_venmo invoked: slack_id={slack_id}, poker_name={poker_name}")
    if not venmo_handle.startswith("@"):
        venmo_handle = "@" + venmo_handle

    try:
        success = db.register_user(slack_id, poker_name, venmo_handle)
        if success:
            logger.info(f"Tool register_player_venmo: success for {slack_id}")
            return {"status": "success", "data": "Registration successful!", "error_message": None}
        logger.error(f"Tool register_player_venmo: DB failure for {slack_id}")
        return {
            "status": "failure",
            "data": "Registration failed.",
            "error_message": "Database operation returned failure status.",
        }
    except Exception as e:
        logger.exception("Error in register_player_venmo")
        return {
            "status": "failure",
            "data": "Registration failed due to an exception.",
            "error_message": str(e),
        }
