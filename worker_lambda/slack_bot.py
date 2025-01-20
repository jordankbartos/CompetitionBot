import json
import logging
import os
import re
import boto3
# import hmac
# import hashlib
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from openai import OpenAI

from event_bridge_trigger import handle_event_bridge_trigger
from config import SYSTEM_PROMPT

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)


slack_token = os.environ['SLACK_BOT_TOKEN']
client = WebClient(token=slack_token)

# def verify_slack_request(headers, body):
#     timestamp = headers["X-Slack-Request-Timestamp"]
#     slack_signature = headers["X-Slack-Signature"]
# 
#     # Prevent replay attacks
#     if abs(time.time() - int(timestamp)) > 60 * 5:
#         raise Exception("Request is outdated")
# 
#     # Create the signature base string
#     base_string = f"v0:{timestamp}:{body}".encode("utf-8")
# 
#     # Generate the hash
#     my_signature = "v0=" + hmac.new(
#         SLACK_SIGNING_SECRET.encode("utf-8"),
#         base_string,
#         hashlib.sha256
#     ).hexdigest()
# 
#     # Compare signatures
#     if not hmac.compare_digest(my_signature, slack_signature):
#         raise Exception("Invalid request signature")

def lambda_handler(event, context):

    logger.info(f"Event: {event}")
    logger.info(f"Context: {context}")

    process_event(event, context)

    return {
        "statusCode": 200,
        "body": "Acknowledged"
    }

def last_n_messages(client, channel_id, n):
    try:
        response = client.conversations_history(
            channel=channel_id,
            limit=n
        )
        messages = response.get("messages", [])[::-1]
        return messages
    except SlackApiError as e:
        logger.exception(e)
        raise

def user_lookup_table(client):
    try:
        # Fetch all users in the workspace
        response = client.users_list()
        users = response.get("members", [])
        
        # Create a lookup table: user_id -> display_name
        user_lookup = {}
        for user in users:
            if not user.get("deleted"):  # Exclude deleted users
                user_lookup[user["id"]] = user["profile"]["display_name"] or user["real_name"]
        return user_lookup
    except SlackApiError as e:
        logger.exception(f"Error fetching user list: {e.response['error']}")
        return {}

def user_ids_to_display(text, user_map):
    uid_pattern = r"<@([A-Z0-9]+)>"

    def replacer(match):
        uid = match.group(1)
        return user_map.get(uid, f"<@{uid}>")

    ret = re.sub(uid_pattern, replacer, text)
    logger.info(f"Subbed '{text}' with '{ret}'")
    return ret

def display_to_user_ids(text, user_map):
    rev_user_map = {name: uid for uid, name in user_map.items()}
    name_pattern = r"\b(" + "|".join(map(re.escape, rev_user_map.keys())) + r")\b"
    def replacer(match):
        name = match.group(1)
        return f"<@{rev_user_map.get(name)}>"
    ret = re.sub(name_pattern, replacer, text)
    logger.info(f"Subbed '{text}' with '{ret}'")
    return ret

    
def slack_to_openai_messages(messages, user_map):
    ret = []
    for m in messages:

        if m['user'] == 'U07D8V4D145':
            role = "assistant"
        else:
            role = "user"

        ret.append(
            {
                "role": role,
                "content": user_ids_to_display(m['text'], user_map)
            }
        )
    return ret

def process_event(event, context):

    if event.get('source') == 'aws.events':
        ret = handle_event_bridge_trigger(event, context)
    else:
        try:
            if "original_event" in event:
                body = event['original_event']
            else:
                body = json.loads(event['body'])
            if 'challenge' in body:
                ret = {
                    'statusCode': 200,
                    'body': json.dumps(body['challenge'])
                }
            elif 'event' in body:

                event_data = body['event']

                if event_data['type'] == 'app_mention' and 'subtype' not in event_data:

                    user_map = user_lookup_table(client)

                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT}
                    ] + slack_to_openai_messages(last_n_messages(client, channel_id=event_data['channel'], n=40), user_map)
                    logger.info(f"{messages=}")

                    ai_client = OpenAI()

                    logger.info("Making request to OpenAI")

                    completion = ai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=1.0,
                    )

                    text = display_to_user_ids(completion.choices[0].message.content, user_map)
                    logger.info(f"Respone: {text}")

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

    