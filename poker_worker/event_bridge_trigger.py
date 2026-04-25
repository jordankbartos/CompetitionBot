import datetime
import os
import random
import time
from typing import Dict, Optional

from ai_news import post_ai_news_digest
from config import AI_CHANNEL_ID, POKER_EMOJIS
from logging_utils import get_logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from database import PokerDatabase

# Logging configuration
logger = get_logger(__name__)


target_channel = "testbots"  # get_env("POKER_CHANNEL") or "pokerrrr"
db = PokerDatabase()


def handle_event_bridge_trigger(event, context):
    logger.info(f"Invoked handle_event_bridge_trigger for event: {event.get('detail-type', 'N/A')}")
    logger.info("Handling EventBridge trigger for weekly poker poll")
    slack_client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

    if not (channel_id := _get_channel_id_by_name(slack_client, target_channel)):
        logger.error(f"handle_event_bridge_trigger: Target channel {target_channel} not found.")
        return {"statusCode": 404, "body": "Channel not found"}

    now = datetime.datetime.now()
    week_label, week_id = _get_next_monday_info(now)
    emoji_mapping = _get_emoji_mapping()

    poll_text = (
        f"*Weekly Poker Poll (week of {week_label})*\nWhich day works best for a game this week?\n"
    )
    for emoji, day in emoji_mapping.items():
        poll_text += f":{emoji}: {day}\n"

    response = _try_post_message(slack_client, channel_id, poll_text)
    if not response:
        logger.error("handle_event_bridge_trigger: Failed to post poll message to Slack.")
        _try_post_message(
            slack_client, channel_id, ":x: Weekly poker poll failed to post. Check the logs."
        )
        return {"statusCode": 500, "body": "Failed to send poll"}

    message_ts = response["ts"]

    logger.info(
        f"handle_event_bridge_trigger: Posted poll message with timestamp {message_ts}. Adding reactions..."
    )
    for emoji in emoji_mapping.keys():
        _try_add_reaction(slack_client, channel_id, message_ts, emoji)
        time.sleep(2)  # Added 2-second delay to guarantee Slack backend ordering

    # 4. Save metadata to DB
    db.save_poll_metadata(week_id, channel_id, message_ts, emoji_mapping)
    logger.info("handle_event_bridge_trigger: Poll sent and metadata saved successfully.")

    # 5. Post AI news digest — runs independently; failure does not affect poll result
    try:
        success = post_ai_news_digest(
            slack_client=slack_client,
            google_api_key=os.environ["GOOGLE_API_KEY"],
            channel_id=AI_CHANNEL_ID,
        )
        if not success:
            _try_post_message(
                slack_client,
                AI_CHANNEL_ID,
                ":x: Weekly AI news digest failed to generate. Check the logs.",
            )
    except Exception:
        logger.exception("handle_event_bridge_trigger: AI news digest failed (non-fatal)")
        _try_post_message(
            slack_client,
            AI_CHANNEL_ID,
            ":x: Weekly AI news digest failed to generate. Check the logs.",
        )

    return {"statusCode": 200, "body": "Poll sent"}


def _get_channel_id_by_name(client, channel_name):
    logger.info(f"_get_channel_id_by_name invoked for channel_name: {channel_name}")
    try:
        result = client.conversations_list(types=["public_channel", "private_channel"])
        for channel in result["channels"]:
            if channel["name"] == channel_name:
                logger.info(
                    f"_get_channel_id_by_name found channel {channel_name} with ID: {channel['id']}"
                )
                return channel["id"]
        logger.warning(f"_get_channel_id_by_name: Channel {channel_name} not found.")
        return None
    except SlackApiError:
        logger.exception(f"_get_channel_id_by_name failed for channel {channel_name}.")


def _get_next_monday_info(now):
    logger.info(f"_get_next_monday_info invoked for date: {now}")
    curr_day = now
    while curr_day.weekday() != 0:
        curr_day = curr_day + datetime.timedelta(days=1)
    week_label = curr_day.strftime("%B %d, %Y")
    week_id = curr_day.strftime("%Y-W%V")
    logger.info(f"_get_next_monday_info determined next Monday: {week_label}, week_id: {week_id}")
    return week_label, week_id


def _get_emoji_mapping():
    logger.info("_get_emoji_mapping invoked.")
    selected_emojis = random.sample(POKER_EMOJIS, 5)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    emoji_map = dict(zip(selected_emojis, days))
    logger.info(f"_get_emoji_mapping created: {emoji_map}")
    return emoji_map


def _try_add_reaction(slack_client, channel_id, message_ts, emoji):
    logger.info(f"_try_add_reaction invoked for emoji: {emoji}, message_ts: {message_ts}")
    try:
        slack_client.reactions_add(channel=channel_id, timestamp=message_ts, name=emoji)
        logger.info(f"_try_add_reaction successfully added {emoji}")
    except SlackApiError as e:
        logger.warning(
            f"_try_add_reaction failed to add reaction {emoji} to {message_ts}: {e.response['error']}"
        )


def _try_post_message(slack_client, channel_id, text) -> Optional[Dict]:
    logger.info(f"_try_post_message invoked for channel_id: {channel_id}, text length: {len(text)}")
    try:
        response = slack_client.chat_postMessage(channel=channel_id, text=text)
        if response["ok"]:
            logger.info(f"_try_post_message successfully posted message with ts: {response['ts']}")
            return response
        else:
            logger.error(f"_try_post_message failed to post: {response['error']}")
            return None
    except SlackApiError:
        logger.exception("_try_post_message encountered SlackApiError.")
        return None
