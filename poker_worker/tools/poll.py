"""
Tool for retrieving weekly poker poll results.
"""

import datetime
from typing import Any, Dict

from logging_utils import get_logger
from slack_sdk.errors import SlackApiError

logger = get_logger(__name__)


def get_weekly_poll_results(db: Any, slack_client: Any) -> Dict[str, Any]:
    """Fetches the current vote tally for the weekly game poll.

    Args:
        db: PokerDatabase instance.
        slack_client: Slack WebClient instance.

    Returns:
        Dict[str, Any] with keys:
          - "status": "success" or "failure"
          - "data": formatted vote tally string or None.
          - "error_message": error details or None.
    """
    logger.info("Tool get_weekly_poll_results invoked.")
    try:
        now = datetime.datetime.now()
        week_id = now.strftime("%Y-W%V")
        poll_metadata = db.get_poll_metadata(week_id)

        if not poll_metadata:
            logger.info("Tool get_weekly_poll_results: no poll found for this week.")
            return {
                "status": "success",
                "data": "No poll found for this week.",
                "error_message": None,
            }

        response = slack_client.reactions_get(
            channel=poll_metadata["channel_id"], timestamp=poll_metadata["message_ts"]
        )
        message = response.get("message") or {}
        reactions = message.get("reactions", [])
        emoji_mapping = poll_metadata["emoji_mapping"]

        tally = {day: 0 for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]}
        for reaction in reactions:
            emoji_name = reaction["name"]
            if emoji_name in emoji_mapping:
                day = emoji_mapping[emoji_name]
                # Subtract 1 to account for the bot's own seed reaction
                count = max(0, reaction["count"] - 1)
                tally[day] = count

        sorted_days = sorted(tally.items(), key=lambda x: x[1], reverse=True)
        lines = ["*Current Poll Results:*"]
        for day, count in sorted_days:
            lines.append(f"- {day}: {count} vote(s)")

        logger.info("Tool get_weekly_poll_results: success.")
        return {"status": "success", "data": "\n".join(lines), "error_message": None}
    except SlackApiError as e:
        logger.exception("Tool get_weekly_poll_results: Slack API error.")
        return {
            "status": "failure",
            "data": None,
            "error_message": f"Failed to get poll results: {e.response.get('error', str(e))}",
        }
    except Exception as e:
        logger.exception("Error in get_weekly_poll_results")
        return {"status": "failure", "data": None, "error_message": str(e)}
