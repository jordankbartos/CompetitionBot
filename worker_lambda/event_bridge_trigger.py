import logging
import os
import re
import datetime
import json

import boto3
from openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import SYSTEM_PROMPT

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

target_channel = "exercise"

def next_monday(given_date):
    # Calculate how many days until the next Monday (0=Monday, 6=Sunday)
    days_until_monday = (7 - given_date.weekday()) % 7
    if days_until_monday == 0:  # If the given date is already a Monday
        days_until_monday = 7
    target_date = given_date + datetime.timedelta(days=days_until_monday)
    return datetime.datetime(year=target_date.year, month=target_date.month, day=target_date.day, hour=2, tzinfo=datetime.UTC)

def handle_event_bridge_trigger(event, context):
    logger.info("handling event bridge trigger")
    logger.debug("instantiating clients")
    events_client = boto3.client('events')
    ai_client = OpenAI()
    slack_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

    # get rule name and ARN from event resources
    if rule_match := re.match(
        pattern=r"^(?P<arn>[\w:\-]+)/(?P<rule_name>[a-zA-Z\-_]+)$",
        string=event['resources'][0]
    ):
        gd = rule_match.groupdict()
        rule_name = gd["rule_name"]
    else:
        raise ValueError("Could not get rule ARN and name from event resources")

    # get previous advices given
    logger.info("Getting previous advices from dynamodb table")
    dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
    table = dynamodb.Table(os.environ["DYNAMODB_TABLE"])
    advice_id = "0"
    logger.info("Getting previous advices from dynamodb table")
    try:
        response = table.get_item(Key={"advice_id": advice_id})
        item = response.get("Item")

        if item is None: # first time, no previous advices exist
            item = {"advice_id": advice_id, "previous_advice": []}
        elif item['previous_advice'] is None:
            item['previous_advice'] = []

        logger.info(f"{item=}")
    except Exception as e:
        logger.error(e)


    previous_messages = [{"role": "assistant", "content": m} for m in item["previous_advice"]]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + previous_messages + [
        {
            "role": "user",
            "content": (
                "Do not give me the same advice you have given previously. Give me a random tip or fact related to "
                "fitness, exercising, or nutrition that is not common knowledge. Use emojis to make it more engaging."
            )
        }
    ]
    logger.info(f"{messages=}")

    # generate message and send it
    logger.info("getting message from OpenAI")
    completion = ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=1.0,
    )
    advice = completion.choices[0].message.content

    channel_id = _get_channel_id_by_name(slack_client, target_channel)
    if channel_id is None:
        raise ValueError(f"Could not find channel ID for '{target_channel}'")

    logger.info(f"sending message to slack channel {channel_id}")

    response = slack_client.chat_postMessage(
        channel=channel_id,
        text=advice
    )

    logger.info("Generating summary of advice")
    summary = ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Give me the topic of this piece of advice in about 10 words. ADVICE: {advice}"}]
    )
    logger.info(f"{summary=}")


    logger.info("Saving summary to db")
    try:
        item['previous_advice'] = item['previous_advice'] + [summary.choices[0].message.content]
        table.put_item(Item=item)
    except Exception as e:
        logger.exception("Saving failed!")

    if response['ok']:
        logger.info('Message sent successfully')
    else:
        logger.error('Failed to send message')

    # create new EventBridge rule
    logger.info("creating new EventBridge rule")
    next_trigger_time = next_monday(datetime.datetime.now(datetime.UTC))
    # next_trigger_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=30) #+ random.randint(-10, 10))
    logger.info(f"next trigger time: {next_trigger_time}")
    cron_expression = (
        f"cron({next_trigger_time.minute} {next_trigger_time.hour} {next_trigger_time.day} {next_trigger_time.month} ? "
        f"{next_trigger_time.year})"
    )
    events_client.put_rule(
        Name=rule_name,
        ScheduleExpression=cron_expression,
        State="ENABLED",
    )

    return {
        'statusCode': 200,
        'body': json.dumps('Success')
    }

def _get_channel_id_by_name(client, channel_name):
    try:
        # Call the conversations.list method using the WebClient
        result = client.conversations_list(types=["public_channel", "private_channel"])
        logger.debug(f"got channels: {', '.join([ch['name'] for ch in result['channels']])}")
        
        # Iterate through the channels
        for channel in result['channels']:
            if channel['name'] == channel_name:
                return channel['id']
        
        logger.warning(f"Could not find channel {channel_name}")
        return None
    
    except SlackApiError as e:
        logger.exception(f"Error fetching conversations: {e.response['error']}")
        return None