"""
Tools for poker game settlement: calculating debt splits, recording results,
and correcting previously recorded games.
"""

import datetime
import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from logging_utils import get_logger

from settlement import calculate_settlements, generate_venmo_link

logger = get_logger(__name__)


def calculate_poker_settlements(player_results: List[Dict[str, Any]], db: Any) -> Dict[str, Any]:
    """Calculates the debt split and generates Venmo payment links for a game.

    Args:
        player_results: List of dicts with 'name' (str) and 'amount' (float in DOLLARS).
        db: PokerDatabase instance.

    Returns:
        Dict with "status", "data" (formatted settlement plan string), "error_message".
    """
    logger.info("Tool calculate_poker_settlements invoked")
    logger.debug(f"calculate_poker_settlements payload: {player_results}")
    try:
        player_data: Dict[str, float] = {}
        for item in player_results:
            clean_name = re.sub(r"\(.*?\)", "", item["name"]).strip()
            player_data[clean_name] = player_data.get(clean_name, 0.0) + float(item["amount"])

        splits = calculate_settlements(player_data)
        if not splits:
            logger.info("Tool calculate_poker_settlements: everyone is even.")
            return {
                "status": "success",
                "data": "Everyone is even! No settlements needed.",
                "error_message": None,
            }

        users = db.get_all_users()
        poker_to_venmo = {u["poker_name"].lower().strip(): u["venmo_handle"] for u in users}
        poker_to_slack = {
            u["poker_name"].lower().strip(): u["PK"].replace("USER#", "") for u in users
        }

        lines = ["*Settlement Plan:*"]
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
                    f"Tool calculate_poker_settlements: {creditor_poker} not registered for Venmo."
                )
                link_text = f"Please register {creditor_poker} to get Venmo links!"

            lines.append(f"- {debtor_tag} pays *{creditor_poker}* ${amount:.2f} - {link_text}")

        logger.info("Tool calculate_poker_settlements: success.")
        return {"status": "success", "data": "\n".join(lines), "error_message": None}
    except Exception as e:
        logger.exception("Error in calculate_poker_settlements")
        return {"status": "failure", "data": None, "error_message": str(e)}


def record_game_result(
    player_results: List[Dict[str, Any]],
    uploader_id: str,
    jordan_id: str,
    db: Any,
    game_id: Optional[str] = None,
    force_overwrite: bool = False,
) -> Dict[str, Any]:
    """Saves game results to the database and updates the leaderboard.

    Args:
        player_results: List of dicts with 'name' and 'amount' (float in DOLLARS).
        uploader_id: Slack ID of the person uploading.
        jordan_id: Slack ID of Jordan (the admin).
        db: PokerDatabase instance.
        game_id: Optional unique game identifier.
        force_overwrite: True only if Jordan explicitly authorised an overwrite.

    Returns:
        Dict with "status", "data", "error_message".
    """
    logger.info(
        f"Tool record_game_result invoked: uploader={uploader_id}, game_id={game_id}, "
        f"force_overwrite={force_overwrite}"
    )
    logger.debug(f"record_game_result payload: {player_results}")

    try:
        player_data: Dict[str, float] = {}
        for item in player_results:
            clean_name = re.sub(r"\(.*?\)", "", item["name"]).strip()
            player_data[clean_name] = player_data.get(clean_name, 0.0) + float(item["amount"])

        sorted_data = sorted(player_data.items())
        fingerprint = hashlib.md5(json.dumps(sorted_data).encode()).hexdigest()

        if not game_id:
            game_id = f"AUTO-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        recent_games = db.get_recent_games(limit=26)

        # Exact duplicate check
        for game in recent_games:
            if game.get("fingerprint") == fingerprint:
                logger.warning(
                    f"Tool record_game_result: exact duplicate found, recorded by {game['uploader_id']}"
                )
                return {
                    "status": "failure",
                    "data": None,
                    "error_message": (
                        f"Error: This exact game was already recorded by <@{game['uploader_id']}>."
                    ),
                }

        # Possible update check (same players within 48 hours)
        current_players = set(player_data.keys())
        for game in recent_games:
            prev_players = set(game["player_data"].keys())
            if current_players == prev_players:
                prev_ts = datetime.datetime.fromisoformat(game["timestamp"])
                if (datetime.datetime.utcnow() - prev_ts).total_seconds() < 172800:
                    if not force_overwrite:
                        logger.warning(
                            "Tool record_game_result: similar recent game found, requesting auth."
                        )
                        return {
                            "status": "failure",
                            "data": None,
                            "error_message": (
                                "It looks like a game with these same players was recorded recently. "
                                f"Jordan (<@{jordan_id}>), can you confirm if I should overwrite "
                                "the previous record with this new data?"
                            ),
                        }
                    elif uploader_id != jordan_id:
                        logger.warning(
                            f"Tool record_game_result: overwrite attempted by non-admin {uploader_id}"
                        )
                        return {
                            "status": "failure",
                            "data": None,
                            "error_message": (
                                f"I need Jordan (<@{jordan_id}>) to authorize overwriting a recent "
                                "game record."
                            ),
                        }

        success = db.save_game(game_id, player_data, fingerprint, uploader_id)
        if success:
            logger.info(f"Tool record_game_result: saved game {game_id}")
            return {
                "status": "success",
                "data": f"Game results recorded successfully! ID: {game_id}",
                "error_message": None,
            }
        logger.error(f"Tool record_game_result: DB save failed for game {game_id}")
        return {
            "status": "failure",
            "data": None,
            "error_message": "Failed to record game results.",
        }
    except Exception as e:
        logger.exception("Error in record_game_result")
        return {"status": "failure", "data": None, "error_message": str(e)}


def find_recent_game(
    search_term: Optional[str],
    db: Any,
    limit: int = 10,
) -> Dict[str, Any]:
    """Searches recent game records by game_id or player name.

    Used when correcting previously recorded games.

    Args:
        search_term: A game ID substring or player name to search for.
                     Pass None or empty string to return the most recent games.
        db: PokerDatabase instance.
        limit: Maximum number of games to return (default 10).

    Returns:
        Dict with "status", "data" (list of matching game summaries), "error_message".
    """
    logger.info(f"Tool find_recent_game invoked: search_term={search_term!r}, limit={limit}")
    try:
        games = db.get_recent_games(limit=limit)
        if not games:
            return {"status": "success", "data": [], "error_message": None}

        if search_term:
            term_lower = search_term.lower().strip()
            games = [
                g
                for g in games
                if term_lower in g.get("PK", "").lower()
                or any(term_lower in name.lower() for name in g.get("player_data", {}).keys())
            ]

        summaries = []
        for game in games:
            game_id = game.get("PK", "").replace("GAME#", "")
            summaries.append(
                {
                    "game_id": game_id,
                    "timestamp": game.get("timestamp"),
                    "uploader_id": game.get("uploader_id"),
                    "players": dict(game.get("player_data", {})),
                }
            )

        logger.info(f"Tool find_recent_game: returning {len(summaries)} results.")
        return {"status": "success", "data": summaries, "error_message": None}
    except Exception as e:
        logger.exception("Error in find_recent_game")
        return {"status": "failure", "data": None, "error_message": str(e)}


def overwrite_game_result(
    game_id: str,
    player_results: List[Dict[str, Any]],
    uploader_id: str,
    jordan_id: str,
    db: Any,
) -> Dict[str, Any]:
    """Overwrites an existing game record with corrected results.

    This is a destructive operation. Requires Jordan's authorisation.

    Args:
        game_id: The exact game ID to overwrite.
        player_results: Corrected list of dicts with 'name' and 'amount' (DOLLARS).
        uploader_id: Slack ID of the person requesting the correction.
        jordan_id: Slack ID of Jordan (the admin).
        db: PokerDatabase instance.

    Returns:
        Dict with "status", "data", "error_message".
    """
    logger.info(f"Tool overwrite_game_result invoked: game_id={game_id}, uploader={uploader_id}")

    if uploader_id != jordan_id:
        logger.warning(f"Tool overwrite_game_result: unauthorised attempt by {uploader_id}")
        return {
            "status": "failure",
            "data": None,
            "error_message": (
                f"Only Jordan (<@{jordan_id}>) can authorise overwriting a game record. "
                "Please ask Jordan to confirm."
            ),
        }

    try:
        player_data: Dict[str, float] = {}
        for item in player_results:
            clean_name = re.sub(r"\(.*?\)", "", item["name"]).strip()
            player_data[clean_name] = player_data.get(clean_name, 0.0) + float(item["amount"])

        sorted_data = sorted(player_data.items())
        fingerprint = hashlib.md5(json.dumps(sorted_data).encode()).hexdigest()

        success = db.save_game(game_id, player_data, fingerprint, uploader_id)
        if success:
            logger.info(f"Tool overwrite_game_result: overwrote game {game_id}")
            return {
                "status": "success",
                "data": f"Game {game_id} updated successfully.",
                "error_message": None,
            }
        return {
            "status": "failure",
            "data": None,
            "error_message": f"Failed to overwrite game {game_id}.",
        }
    except Exception as e:
        logger.exception(f"Error in overwrite_game_result for game {game_id}")
        return {"status": "failure", "data": None, "error_message": str(e)}


def delete_game_result(
    game_id: str,
    uploader_id: str,
    jordan_id: str,
    db: Any,
) -> Dict[str, Any]:
    """Permanently deletes a game record and its associated player stats.

    This is a destructive operation. Requires Jordan's authorisation.

    Args:
        game_id: The exact game ID to delete.
        uploader_id: Slack ID of the person requesting deletion.
        jordan_id: Slack ID of Jordan (the admin).
        db: PokerDatabase instance.

    Returns:
        Dict with "status", "data", "error_message".
    """
    logger.info(f"Tool delete_game_result invoked: game_id={game_id}, uploader={uploader_id}")

    if uploader_id != jordan_id:
        logger.warning(f"Tool delete_game_result: unauthorised attempt by {uploader_id}")
        return {
            "status": "failure",
            "data": None,
            "error_message": (
                f"Only Jordan (<@{jordan_id}>) can authorise deleting a game record. "
                "Please ask Jordan to confirm."
            ),
        }

    try:
        success = db.delete_game(game_id)
        if success:
            logger.info(f"Tool delete_game_result: deleted game {game_id}")
            return {
                "status": "success",
                "data": f"Game {game_id} deleted successfully.",
                "error_message": None,
            }
        return {
            "status": "failure",
            "data": None,
            "error_message": f"Failed to delete game {game_id}.",
        }
    except Exception as e:
        logger.exception(f"Error in delete_game_result for game {game_id}")
        return {"status": "failure", "data": None, "error_message": str(e)}


def rename_player_in_game_history(
    old_name: str,
    new_name: str,
    uploader_id: str,
    jordan_id: str,
    db: Any,
) -> Dict[str, Any]:
    """Renames a player across all historical game records and leaderboard stats.

    Use this to consolidate name variants caused by OCR mis-reads
    (e.g. merging 'Reece (left)' and 'Reece' into a single canonical name).
    All amounts for old_name are merged into new_name; if new_name already
    appears in the same game, the amounts are summed.

    This is a destructive bulk operation. Requires Jordan's authorisation.

    Args:
        old_name: The player name to remove/replace (exact string as stored in DB,
                  case-insensitive match).
        new_name: The canonical player name to merge into.
        uploader_id: Slack ID of the person requesting the rename.
        jordan_id: Slack ID of Jordan (the admin).
        db: PokerDatabase instance.

    Returns:
        Dict with "status", "data" (summary of changes), "error_message".
    """
    logger.info(
        f"Tool rename_player_in_game_history: '{old_name}' -> '{new_name}', "
        f"requested by {uploader_id}"
    )

    if uploader_id != jordan_id:
        logger.warning(f"Tool rename_player_in_game_history: unauthorised attempt by {uploader_id}")
        return {
            "status": "failure",
            "data": None,
            "error_message": (
                f"Only Jordan (<@{jordan_id}>) can authorise renaming a player across "
                "all historical records. Please ask Jordan to confirm."
            ),
        }

    if not old_name.strip() or not new_name.strip():
        return {
            "status": "failure",
            "data": None,
            "error_message": "old_name and new_name must both be non-empty strings.",
        }

    try:
        summary = db.rename_player_across_all_games(old_name=old_name, new_name=new_name)
        games_updated = summary.get("games_updated", 0)
        stats_updated = summary.get("stats_updated", 0)

        if games_updated == 0:
            logger.info(f"Tool rename_player_in_game_history: no games found for '{old_name}'")
            return {
                "status": "success",
                "data": (f"No game records found containing '{old_name}'. Nothing was changed."),
                "error_message": None,
            }

        logger.info(
            f"Tool rename_player_in_game_history: updated {games_updated} games, "
            f"{stats_updated} stat entries."
        )
        return {
            "status": "success",
            "data": (
                f"Renamed '{old_name}' to '{new_name}' across {games_updated} game record(s) "
                f"and {stats_updated} leaderboard stat entry/entries."
            ),
            "error_message": None,
        }
    except Exception as e:
        logger.exception(f"Error in rename_player_in_game_history: '{old_name}' -> '{new_name}'")
        return {"status": "failure", "data": None, "error_message": str(e)}
