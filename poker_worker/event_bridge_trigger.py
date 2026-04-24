import datetime
import os
import random

from config import POKER_EMOJIS
from logging_utils import get_logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from database import PokerDatabase

# Logging configuration
logger = get_logger(__name__)


target_channel = "testbots"  # get_env("POKER_CHANNEL") or "pokerrrr"
db = PokerDatabase()


def handle_event_bridge_trigger(event, context):
    logger.info("Handling EventBridge trigger for weekly poker poll")
    slack_client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

    if not (channel_id := _get_channel_id_by_name(slack_client, target_channel)):
        return {"statusCode": 404, "body": "Channel not found"}

    now = datetime.datetime.now()
    week_label, week_id = _get_next_monday_info(now)
    emoji_mapping = _get_emoji_mapping()

    poll_text = (
        f"*Weekly Poker Poll (week of {week_label})*\nWhich day works best for a game this week?\n"
    )
    for emoji, day in emoji_mapping.items():
        poll_text += f":{emoji}: {day}\n"

    if not (response := _try_post_message(slack_client, channel_id, poll_text)):
        return {"statusCode": 500, "body": "Failed to send poll"}

    message_ts = response["ts"]

    for emoji in emoji_mapping.keys():
        _try_add_reaction(slack_client, channel_id, message_ts, emoji)

    # 4. Save metadata to DB
    db.save_poll_metadata(week_id, channel_id, message_ts, emoji_mapping)

    logger.info("Poll sent and metadata saved successfully")
    return {"statusCode": 200, "body": "Poll sent"}


def _get_channel_id_by_name(client, channel_name):
    try:
        result = client.conversations_list(types=["public_channel", "private_channel"])
        for channel in result["channels"]:
            if channel["name"] == channel_name:
                return channel["id"]
        return None
    except SlackApiError as e:
        logger.exception(f"Error fetching conversations: {e.response['error']}")
        return None


def _get_next_monday_info(now):
    curr_day = now
    while curr_day.weekday() != 0:
        curr_day = curr_day + datetime.timedelta(days=1)
    week_label = curr_day.strftime("%B %d, %Y")
    week_id = curr_day.strftime("%Y-W%V")
    return week_label, week_id


def _get_emoji_mapping():
    selected_emojis = random.sample(POKER_EMOJIS, 5)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    return dict(zip(selected_emojis, days))


def _try_add_reaction(slack_client, channel_id, message_ts, emoji):
    try:
        slack_client.reactions_add(channel=channel_id, timestamp=message_ts, name=emoji)
    except SlackApiError as e:
        logger.warning(f"Failed to add reaction {emoji}: {e.response['error']}")


def _try_post_message(slack_client, channel_id, text):
    try:
        response = slack_client.chat_postMessage(channel=channel_id, text=text)
    except SlackApiError:
        logger.exception("Error sending poll to Slack")
        return None

    if not response["ok"]:
        logger.error(f"Failed to send poll: {response['error']}")
        return None
    else:
        return response
