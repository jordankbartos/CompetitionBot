"""
Adapters for the LLM agent to interact with the system.
These tools are atomic and provide a bridge between the agent and domain services.
"""

import datetime
import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from logging_utils import get_logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from database import PokerDatabase
from settlement import calculate_settlements as calc_splits
from settlement import generate_venmo_link
from utils import get_env

logger = get_logger(__name__)

JORDAN_ID = "U85D9C8TV"

db = PokerDatabase()
slack_token = get_env("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)

try:
    bot_user_id = client.auth_test()["user_id"]
except Exception:
    logger.warning("Could not find bot_user_id, using fallback")
    bot_user_id = "U07D8V4D145"


def get_user_profile(slack_id: str) -> Optional[Dict[str, str]]:
    """
    Retrieves the poker name and Venmo handle for a Slack user.

    Args:
        slack_id: The Slack user ID (e.g., 'U12345').

    Returns:
        A dictionary with 'poker_name' and 'venmo_handle', or None if not found.
    """
    logger.info(f"Tool get_user_profile invoked with slack_id: {slack_id}")
    profile = db.get_user_by_slack_id(slack_id)
    if profile:
        logger.info(f"Tool get_user_profile completed successfully for slack_id: {slack_id}")
        return {
            "poker_name": profile.get("poker_name", ""),
            "venmo_handle": profile.get("venmo_handle", ""),
        }
    logger.info(f"Tool get_user_profile found no profile for slack_id: {slack_id}")
    return None


def register_player(slack_id: str, poker_name: str, venmo_handle: str) -> str:
    """
    Registers a new player with their poker name and Venmo handle.

    Args:
        slack_id: The Slack user ID.
        poker_name: Their display name in poker games.
        venmo_handle: Their Venmo handle (with or without '@').

    Returns:
        A confirmation message.
    """
    logger.info(
        f"Tool register_player invoked with slack_id: {slack_id}, poker_name: {poker_name}, venmo_handle: {venmo_handle}"
    )
    if not venmo_handle.startswith("@"):
        venmo_handle = "@" + venmo_handle

    success = db.register_user(slack_id, poker_name, venmo_handle)
    if success:
        logger.info(f"Tool register_player completed successfully for slack_id: {slack_id}")
        return "Registration successful!"
    else:
        logger.error(f"Tool register_player failed for slack_id: {slack_id}")
        return "Registration failed."


def calculate_poker_settlements(player_results: List[Dict[str, Any]]) -> str:
    """
    Calculates the debt split and generates Venmo payment links for a game.

    Args:
        player_results: A list of dicts with 'name' (str) and 'amount' (float).

    Returns:
        A formatted string describing who pays whom and Venmo links.
    """
    logger.info(f"Tool calculate_poker_settlements invoked with player_results: {player_results}")
    player_data: Dict[str, float] = {}
    for item in player_results:
        clean_name = re.sub(r"\(.*?\)", "", item["name"]).strip()
        player_data[clean_name] = player_data.get(clean_name, 0.0) + float(item["amount"])

    splits = calc_splits(player_data)
    if not splits:
        logger.info("Tool calculate_poker_settlements: no settlements needed, everyone is even.")
        return "Everyone is even! No settlements needed."

    users = db.get_all_users()
    poker_to_venmo = {u["poker_name"].lower().strip(): u["venmo_handle"] for u in users}
    poker_to_slack = {u["poker_name"].lower().strip(): u["PK"].replace("USER#", "") for u in users}

    response_lines = ["*Settlement Plan:*"]
    for debtor_poker, creditor_poker, amount in splits:
        creditor_key = creditor_poker.lower().strip()
        debtor_key = debtor_poker.lower().strip()

        creditor_venmo = poker_to_venmo.get(creditor_key)
        debtor_slack = poker_to_slack.get(debtor_key)

        debtor_tag = f"<@{debtor_slack}>" if debtor_slack else debtor_poker

        if creditor_venmo:
            v_link = generate_venmo_link(creditor_venmo, amount)
            link_text = f"<{v_link}|Pay {creditor_venmo}>"
        else:
            logger.warning(
                f"Tool calculate_poker_settlements: creditor {creditor_poker} not registered for Venmo."
            )
            link_text = f"Please register {creditor_poker} to get Venmo links!"

        response_lines.append(f"- {debtor_tag} pays *{creditor_poker}* ${amount:.2f} - {link_text}")

    logger.info("Tool calculate_poker_settlements completed successfully, splits generated.")
    return "\n".join(response_lines)


def record_game_result(
    player_results: List[Dict[str, Any]],
    uploader_id: str,
    game_id: Optional[str] = None,
    force_overwrite: bool = False,
) -> str:
    """
    Saves the game results to the database for the leaderboard.

    Args:
        player_results: List of dicts with 'name' and 'amount'.
        uploader_id: Slack ID of the person uploading.
        game_id: Optional unique ID for the game.
        force_overwrite: Set to True ONLY if Jordan has authorized an overwrite of a recent game.

    Returns:
        A status message.
    """
    logger.info(
        f"Tool record_game_result invoked with player_results: {player_results}, uploader_id: {uploader_id}, game_id: {game_id}, force_overwrite: {force_overwrite}"
    )
    # Aggregate data
    player_data: Dict[str, float] = {}
    for item in player_results:
        clean_name = re.sub(r"\(.*?\)", "", item["name"]).strip()
        player_data[clean_name] = player_data.get(clean_name, 0.0) + float(item["amount"])

    sorted_data = sorted(player_data.items())
    fingerprint = hashlib.md5(json.dumps(sorted_data).encode()).hexdigest()

    if not game_id:
        game_id = f"AUTO-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    recent_games = db.get_recent_games(limit=26)
    for game in recent_games:
        if game.get("fingerprint") == fingerprint:
            logger.warning(
                f"Tool record_game_result: exact game already recorded by {game['uploader_id']}"
            )
            return f"Error: This exact game was already recorded by <@{game['uploader_id']}>."

    # Potential update check (same players within 48 hours)
    current_players = set(player_data.keys())
    for game in recent_games:
        prev_players = set(game["player_data"].keys())
        if current_players == prev_players:
            prev_ts = datetime.datetime.fromisoformat(game["timestamp"])
            if (datetime.datetime.utcnow() - prev_ts).total_seconds() < 172800:
                if not force_overwrite:
                    logger.warning(
                        "Tool record_game_result: similar game recorded recently, requesting overwrite authorization."
                    )
                    return (
                        f"It looks like a game with these same players was recorded recently. "
                        f"Jordan (<@{JORDAN_ID}>), can you confirm if I should overwrite the previous record with this new data?"
                    )
                elif uploader_id != JORDAN_ID:
                    logger.warning(
                        f"Tool record_game_result: overwrite requested by non-Jordan user {uploader_id}"
                    )
                    return f"I need Jordan (<@{JORDAN_ID}>) to authorize overwriting a recent game record."

    success = db.save_game(game_id, player_data, fingerprint, uploader_id)
    if success:
        logger.info(f"Tool record_game_result completed successfully for game_id: {game_id}")
        return f"Game results recorded successfully! ID: {game_id}"
    logger.error(f"Tool record_game_result failed to save game_id: {game_id}")
    return "Failed to record game results."


def get_leaderboard() -> str:
    """
    Returns the all-time profit/loss leaderboard.

    Returns:
        A formatted string showing the ranked players.
    """
    logger.info("Tool get_leaderboard invoked.")
    leaderboard = db.get_leaderboard()
    if not leaderboard:
        logger.info("Tool get_leaderboard found no game data.")
        return "No game data found yet!"

    lines = ["*All-Time Leaderboard:*"]
    for i, (name, amount) in enumerate(leaderboard):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "-"
        lines.append(f"{medal} {name.capitalize()}: ${amount:.2f}")

    logger.info("Tool get_leaderboard completed successfully.")
    return "\n".join(lines)


def is_bot_in_thread(channel_id: str, thread_ts: str) -> bool:
    """
    Checks if the bot has already participated in a specific thread.
    Used to determine if the bot should respond to replies in a thread.
    """
    logger.info(
        f"Tool is_bot_in_thread invoked with channel_id: {channel_id}, thread_ts: {thread_ts}"
    )
    try:
        response = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=50)
        messages = response.get("messages", [])
        in_thread = any(msg.get("user") == bot_user_id for msg in messages)
        logger.info(f"Tool is_bot_in_thread completed successfully, bot in thread: {in_thread}")
        return in_thread
    except SlackApiError:
        logger.exception(
            f"Tool is_bot_in_thread failed for channel_id: {channel_id}, thread_ts: {thread_ts}"
        )
        return False


def slack_get_history(channel_id: str, limit: int = 20, thread_ts: Optional[str] = None) -> str:
    """
    Retrieves recent messages from a channel or thread.
    Use this to retrieve conversation history context.

    Args:
        channel_id: The ID of the channel.
        limit: Number of messages to retrieve (default 10).
        thread_ts: The timestamp of the parent message if in a thread.
    """
    logger.info(
        f"Tool slack_get_history invoked with channel_id: {channel_id}, limit: {limit}, thread_ts: {thread_ts}"
    )
    try:
        if thread_ts:
            response = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=limit)
        else:
            response = client.conversations_history(channel=channel_id, limit=limit)

        messages = response.get("messages", [])
        if not thread_ts or thread_ts == "None":
            messages = list(reversed(messages))

        formatted = []
        for msg in messages:
            user = msg.get("user", "Bot")
            text = msg.get("text", "")
            formatted.append(f"<@{user}>: {text}")
        logger.info(
            f"Tool slack_get_history completed successfully for channel_id: {channel_id}, retrieved {len(messages)} messages."
        )
        return "\n".join(formatted)
    except SlackApiError:
        logger.exception(
            f"Tool slack_get_history failed for channel_id: {channel_id}, thread_ts: {thread_ts}"
        )
        return "Failed to retrieve history."


def slack_react(channel_id: str, timestamp: str, emoji: str, action: str = "add") -> str:
    """
    Adds or removes a reaction to a message.

    Args:
        channel_id: The ID of the channel.
        timestamp: The timestamp of the message.
        emoji: The name of the emoji (without colons).
        action: Either 'add' or 'remove'.
    """
    logger.info(
        f"Tool slack_react invoked with channel_id: {channel_id}, timestamp: {timestamp}, emoji: {emoji}, action: {action}"
    )
    try:
        if action == "add":
            client.reactions_add(channel=channel_id, timestamp=timestamp, name=emoji)
            logger.info(
                f"Tool slack_react: added reaction {emoji} to message {timestamp} in channel {channel_id}"
            )
        else:
            client.reactions_remove(channel=channel_id, timestamp=timestamp, name=emoji)
            logger.info(
                f"Tool slack_react: removed reaction {emoji} from message {timestamp} in channel {channel_id}"
            )
        return "Reaction updated."
    except SlackApiError:
        logger.exception(
            f"Tool slack_react failed for channel_id: {channel_id}, timestamp: {timestamp}, emoji: {emoji}, action: {action}"
        )
        return "Failed to update reaction."


def get_weekly_poll_results() -> str:
    """
    Fetches the current status of the weekly game poll.

    Returns:
        A breakdown of votes per day.
    """
    logger.info("Tool get_weekly_poll_results invoked.")
    now = datetime.datetime.now()
    week_id = now.strftime("%Y-W%V")
    poll_metadata = db.get_poll_metadata(week_id)

    if not poll_metadata:
        logger.info("Tool get_weekly_poll_results: no poll found for this week.")
        return "No poll found for this week."

    try:
        response = client.reactions_get(
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
        response_lines = ["*Current Poll Results:*"]
        for day, count in sorted_days:
            response_lines.append(f"- {day}: {count} vote(s)")
        logger.info("Tool get_weekly_poll_results completed successfully, results retrieved.")
        return "\n".join(response_lines)
    except SlackApiError:
        logger.exception("Tool get_weekly_poll_results failed to retrieve poll results.")
        return "Failed to get poll results."
