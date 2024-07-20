import json
import logging
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

print(f"Log level: {log_level}")

logger.critical("hello critical")
logger.error("hello error")
logger.warning("hello warning")
logger.info("hello info")
logger.debug("hello debug")


slack_token = os.environ['SLACK_BOT_TOKEN']
client = WebClient(token=slack_token)


def lambda_handler(event, context):

    logger.info(f"Event: {event}")
    logger.info(f"Context: {context}")

    try:
        body = json.loads(event['body'])
        if 'event' in body:
            event_data = body['event']
            if event_data['type'] == 'message' and 'subtype' not in event_data:
                response = client.chat_postMessage(
                    channel=event_data['channel'],
                    text=f"Hello, <@{event_data['user']}>! How can I assist you today?"
                )
                if response['ok']:
                    logger.info('Message sent successfully')
                else:
                    logger.error('Failed to send message')
        ret = {
            'statusCode': 200,
            'body': json.dumps('Success')
        }
    except SlackApiError as e:
        logger.exception(f"Error: {e.response['error']}")
        ret = {
            'statusCode': 500,
            'body': json.dumps('Error')
        }

    return ret


if __name__ == "__main__":
    event = {
        'body': '{"event": {"type": "message", "channel": "C01U6N4QK3E", "user": "U01U6N4QK3F"}}'
    }
    lambda_handler(event, None)
