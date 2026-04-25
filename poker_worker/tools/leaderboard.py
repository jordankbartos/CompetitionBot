"""
Tool for retrieving the all-time poker leaderboard.
"""

from typing import Any, Dict

from logging_utils import get_logger

logger = get_logger(__name__)


def get_poker_leaderboard(db: Any) -> Dict[str, Any]:
    """Returns the all-time profit/loss leaderboard.

    Args:
        db: PokerDatabase instance.

    Returns:
        Dict[str, Any] with keys:
          - "status": "success" or "failure"
          - "data": formatted leaderboard string or None.
          - "error_message": error details or None.
    """
    logger.info("Tool get_poker_leaderboard invoked.")
    try:
        leaderboard = db.get_leaderboard()
        if not leaderboard:
            logger.info("Tool get_poker_leaderboard: no game data.")
            return {"status": "success", "data": "No game data found yet!", "error_message": None}

        lines = ["*All-Time Leaderboard:*"]
        medals = ["🥇", "🥈", "🥉"] + ["-"] * (len(leaderboard) - 3)
        for (name, amount), medal in zip(leaderboard, medals):
            lines.append(f"{medal} {name.capitalize()}: ${amount:.2f}")

        logger.info("Tool get_poker_leaderboard: success.")
        return {"status": "success", "data": "\n".join(lines), "error_message": None}
    except Exception as e:
        logger.exception("Error in get_poker_leaderboard")
        return {"status": "failure", "data": None, "error_message": str(e)}
