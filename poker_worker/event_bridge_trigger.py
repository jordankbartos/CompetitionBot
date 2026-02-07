import logging
import os
import datetime
import json
import boto3
import random
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import POKER_EMOJIS
from database import PokerDatabase
from utils import get_env

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

target_channel = get_env("POKER_CHANNEL") or "poker"
db = PokerDatabase()

def handle_event_bridge_trigger(event, context):
    logger.info("Handling EventBridge trigger for weekly poker poll")
    slack_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

    channel_id = _get_channel_id_by_name(slack_client, target_channel)
    if not channel_id:
        logger.error(f"Could not find channel {target_channel}")
        return {"statusCode": 404, "body": "Channel not found"}

    now = datetime.datetime.now()
    monday = now - datetime.timedelta(days=now.weekday())
    week_label = monday.strftime("%B %d, %Y")
    week_id = now.strftime("%Y-W%V")
    
    # 1. Pick 5 unique random emojis
    selected_emojis = random.sample(POKER_EMOJIS, 5)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    
    # Create emoji -> day mapping for the DB
    emoji_mapping = {selected_emojis[i]: days[i] for i in range(5)}
    
    # Construct the message
    poll_text = f"*Weekly Poker Poll (week of {week_label})*\nWhich day works best for a game this week?\n"
    for day, emoji in zip(days, selected_emojis):
        poll_text += f":{emoji}: {day}\n"

    try:
        # 2. Post the message
        response = slack_client.chat_postMessage(
            channel=channel_id,
            text=poll_text
        )
        if not response['ok']:
            logger.error(f"Failed to send poll: {response['error']}")
            return {"statusCode": 500, "body": "Failed to send poll"}

        message_ts = response['ts']
        
        # 3. Seed reactions
        for emoji in selected_emojis:
            try:
                slack_client.reactions_add(
                    channel=channel_id,
                    timestamp=message_ts,
                    name=emoji
                )
            except SlackApiError as e:
                logger.warning(f"Failed to add reaction {emoji}: {e.response['error']}")

        # 4. Save metadata to DB
        db.save_poll_metadata(week_id, channel_id, message_ts, emoji_mapping)
        
        logger.info("Poll sent and metadata saved successfully")
        return {"statusCode": 200, "body": "Poll sent"}

    except SlackApiError as e:
        logger.exception("Error sending poll to Slack")
        return {"statusCode": 500, "body": str(e)}

def _get_channel_id_by_name(client, channel_name):
    try:
        result = client.conversations_list(types=["public_channel", "private_channel"])
        for channel in result['channels']:
            if channel['name'] == channel_name:
                return channel['id']
        return None
    except SlackApiError as e:
        logger.exception(f"Error fetching conversations: {e.response['error']}")
        return None
