import json
import logging
import hashlib
import datetime
import re
from database import PokerDatabase
from settlement import calculate_settlements as calc_splits
from settlement import generate_venmo_link
from slack_sdk import WebClient
from utils import get_env

logger = logging.getLogger(__name__)
db = PokerDatabase()
slack_token = get_env('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)

JORDAN_ID = "U85D9C8TV"

def get_user_profile(slack_id: str):
    """Retrieves the poker name and Venmo handle for a Slack user."""
    profile = db.get_user_by_slack_id(slack_id)
    if profile:
        return {
            "poker_name": profile.get("poker_name"),
            "venmo_handle": profile.get("venmo_handle")
        }
    return None

def register_player(slack_id: str, poker_name: str, venmo_handle: str):
    """Registers a new player with their poker name and Venmo handle."""
    if not venmo_handle.startswith('@'):
        venmo_handle = '@' + venmo_handle
    success = db.register_user(slack_id, poker_name, venmo_handle)
    return "Registration successful!" if success else "Registration failed."

from typing import List, Dict, Any

def calculate_poker_settlements(player_results: list):
    """
    Calculates the debt split and generates Venmo payment links.
    Args:
        player_results: List of {'name': str, 'amount': float}
    """
    # Convert list back to dictionary for internal logic and clean names
    player_data = {}
    for item in player_results:
        clean_name = re.sub(r'\(.*?\)', '', item['name']).strip()
        player_data[clean_name] = player_data.get(clean_name, 0.0) + float(item['amount'])
    
    # 1. Calculate splits
    splits = calc_splits(player_data)
    if not splits:
        return "Everyone is even! No settlements needed."

    # 2. Get registered users for Venmo matching
    users = db.get_all_users()
    poker_to_venmo = {u['poker_name'].lower().strip(): u['venmo_handle'] for u in users}
    poker_to_slack = {u['poker_name'].lower().strip(): u['PK'].replace('USER#', '') for u in users}

    response_lines = ["*Settlement Plan:*"]
    for debtor_poker, creditor_poker, amount in splits:
        creditor_key = creditor_poker.lower().strip()
        debtor_key = debtor_poker.lower().strip()
        
        creditor_venmo = poker_to_venmo.get(creditor_key, f"(No Venmo for {creditor_poker})")
        debtor_slack = poker_to_slack.get(debtor_key)
        debtor_tag = f"<@{debtor_slack}>" if debtor_slack else debtor_poker
        
        v_link = generate_venmo_link(creditor_venmo, amount) if "No Venmo" not in creditor_venmo else ""
        link_text = f"<{v_link}|Pay {creditor_venmo}>" if v_link else "Please register to get Venmo links!"
        
        response_lines.append(f"- {debtor_tag} pays *{creditor_poker}* ${amount:.2f} - {link_text}")
        
    return "\n".join(response_lines)

def record_game_result(player_results: list, uploader_id: str, game_id: str = "", force_overwrite: bool = False):
    """
    Saves the game results to the database for the leaderboard.
    Args:
        player_results: List of {'name': str, 'amount': float}
        uploader_id: Slack ID of the person uploading
        game_id: Optional ID from the poker app
        force_overwrite: Set to True ONLY if Jordan has authorized an overwrite
    """
    # Convert list back to dictionary for internal logic and clean names
    player_data = {}
    for item in player_results:
        clean_name = re.sub(r'\(.*?\)', '', item['name']).strip()
        player_data[clean_name] = player_data.get(clean_name, 0.0) + float(item['amount'])
    
    # Generate fingerprint (sorted players + amounts)
    sorted_data = sorted(player_data.items())
    fingerprint = hashlib.md5(json.dumps(sorted_data).encode()).hexdigest()
    
    # If no game_id, use timestamp
    if not game_id:
        game_id = f"AUTO-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"


    # Check for duplicates in recent games
    recent_games = db.get_recent_games(limit=10)
    
    # 1. Exact Duplicate Check
    for game in recent_games:
        if game.get('fingerprint') == fingerprint:
            return f"Error: This exact game was already recorded by <@{game['uploader_id']}>."

    # 2. Potential Update Check (Same players, different amounts, within 4 hours)
    current_players = set(player_data.keys())
    for game in recent_games:
        prev_players = set(game['player_data'].keys())
        if current_players == prev_players:
            # Check time diff
            prev_ts = datetime.datetime.fromisoformat(game['timestamp'])
            if (datetime.datetime.utcnow() - prev_ts).total_seconds() < 14400: # 4 hours
                if not force_overwrite:
                    return (f"It looks like a game with these same players was recorded recently. "
                            f"Jordan (<@{JORDAN_ID}>), can you confirm if I should overwrite the previous record with this new data?")
                elif uploader_id != JORDAN_ID:
                    return f"I need Jordan (<@{JORDAN_ID}>) to authorize overwriting a recent game record."
                else:
                    # Proceed with overwrite
                    pass

    success = db.save_game(game_id, player_data, fingerprint, uploader_id)
    if success:
        return f"Game results recorded successfully! ID: {game_id}"
    return "Failed to record game results."

def get_leaderboard():
    """Returns the all-time profit/loss leaderboard."""
    leaderboard = db.get_leaderboard()
    if not leaderboard:
        return "No game data found yet!"
    
    lines = ["*All-Time Leaderboard:*"]
    for i, (name, amount) in enumerate(leaderboard):
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "-"
        lines.append(f"{medal} {name.capitalize()}: ${amount:.2f}")
    
    return "\n".join(lines)

def is_bot_in_thread(channel_id: str, thread_ts: str):
    """Checks if the bot has already participated in a specific thread."""
    try:
        response = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=20)
        messages = response.get('messages', [])
        for msg in messages:
            if msg.get('user') == "U07D8V4D145":
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking thread participation: {e}")
        return False

def slack_get_history(channel_id: str, limit: int = 10, thread_ts: str = None):
    """
    Retrieves recent messages from a channel or thread. Use this tool to provide context, 
    summarize conversations, or see what was discussed previously.
    Args:
        channel_id: The ID of the channel to read from.
        limit: The number of messages to retrieve (default 10).
        thread_ts: The timestamp of the parent message if the conversation is in a thread.
    """
    try:
        if thread_ts and thread_ts != "None":
            response = client.conversations_replies(channel=channel_id, ts=thread_ts, limit=limit)
        else:
            response = client.conversations_history(channel=channel_id, limit=limit)
        
        messages = response.get('messages', [])
        # Format for agent
        formatted = []
        # Reverse if it's history to get chronological order for the agent? 
        # Slack returns newest first for history, but oldest first for replies.
        # Let's just ensure we have a consistent view.
        if not thread_ts or thread_ts == "None":
            messages = reversed(messages)

        for msg in messages:
            user = msg.get('user', 'Bot')
            text = msg.get('text', '')
            formatted.append(f"<@{user}>: {text}")
        return "\n".join(formatted)
    except Exception as e:
        return f"Failed to get history: {str(e)}"

def slack_react(channel_id: str, timestamp: str, emoji: str, action: str = "add"):
    """Adds or removes a reaction to a message."""
    try:
        if action == "add":
            client.reactions_add(channel=channel_id, timestamp=timestamp, name=emoji)
        else:
            client.reactions_remove(channel=channel_id, timestamp=timestamp, name=emoji)
        return "Reaction updated."
    except Exception as e:
        return f"Failed to update reaction: {str(e)}"

def get_weekly_poll_results():
    """Fetches the current status of the weekly game poll."""
    # Logic from slack_bot.py handle_poll_results
    now = datetime.datetime.now()
    week_id = now.strftime("%Y-W%V")
    poll_metadata = db.get_poll_metadata(week_id)
    
    if not poll_metadata:
        return "No poll found for this week."

    try:
        response = client.reactions_get(
            channel=poll_metadata['channel_id'],
            timestamp=poll_metadata['message_ts']
        )
        message = response['message']
        reactions = message.get('reactions', [])
        emoji_mapping = poll_metadata['emoji_mapping']
        
        tally = {day: 0 for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]}
        for reaction in reactions:
            emoji_name = reaction['name']
            if emoji_name in emoji_mapping:
                day = emoji_mapping[emoji_name]
                count = max(0, reaction['count'] - 1)
                tally[day] = count
        
        sorted_days = sorted(tally.items(), key=lambda x: x[1], reverse=True)
        response_lines = ["*Current Poll Results:*"]
        for day, count in sorted_days:
            response_lines.append(f"- {day}: {count} vote(s)")
        return "\n".join(response_lines)
    except Exception as e:
        return f"Failed to get poll: {str(e)}"
