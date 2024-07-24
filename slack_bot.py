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

                ai_client = OpenAI()

                completion = ai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an evil and possessed robot hell-bent on making everyone as strong and as fit "
                                "as possible. You motivate people to exercise through intimidation, fear, and threats. "
                                "Keep your responses short and to the point. Try not to exceed 140 characters."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "Compose a message that informs somebody that you can't help them with their request. "
                                f"Their request: {event_data['text']}"
                            )
                        },
                    ],
                    temperature=1.0,
                )

                text=f"<@{event_data['user']}> {completion.choices[0].message.content}"

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

    