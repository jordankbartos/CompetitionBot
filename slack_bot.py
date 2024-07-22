import json
import logging
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from openai import OpenAI

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)


slack_token = os.environ['SLACK_BOT_TOKEN']
client = WebClient(token=slack_token)


def lambda_handler(event, context):

    logger.info(f"Event: {event}")
    logger.info(f"Context: {context}")

    try:
        body = json.loads(event['body'])
        if 'challenge' in body:
            ret = {
                'statusCode': 200,
                'body': json.dumps(body['challenge'])
            }
        elif 'event' in body:

            event_data = body['event']

            if event_data['type'] == 'app_mention' and 'subtype' not in event_data:

                client = OpenAI()
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an evil workout robot, motivating people to exercise through intimidation and fear."},
                        {"role": "user", "content": "Compose a message that informs somebody you don't know what they want, but they should be working out instead of asking you pointless questions."}
                    ]
                )

                text=f"Hey, <@{event_data['user']}>. {completion.choices[0].message}"

                response = client.chat_postMessage(
                    channel=event_data['channel'],
                    text=text,
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

    logger.info(f"Response: {ret}")
    return ret

    