import logging
import os
import datetime
import json
import boto3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

target_channel = os.environ.get("POKER_CHANNEL", "poker")

def handle_event_bridge_trigger(event, context):
    logger.info("Handling EventBridge trigger for weekly poker poll")
    slack_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

    channel_id = _get_channel_id_by_name(slack_client, target_channel)
    if not channel_id:
        logger.error(f"Could not find channel {target_channel}")
        return {"statusCode": 404, "body": "Channel not found"}

    week_id = datetime.datetime.now().strftime("%Y-W%V")
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Weekly Poker Poll ({week_id})*\nWhich day works best for a game this week?"
            }
        },
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": day}, "action_id": f"poll_vote_{day}"}
                for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            ]
        }
    ]

    try:
        response = slack_client.chat_postMessage(
            channel=channel_id,
            blocks=blocks,
            text="Weekly Poker Poll" # Fallback text
        )
        if response['ok']:
            logger.info("Poll sent successfully")
            return {"statusCode": 200, "body": "Poll sent"}
        else:
            logger.error(f"Failed to send poll: {response['error']}")
            return {"statusCode": 500, "body": "Failed to send poll"}
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
