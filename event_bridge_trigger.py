import logging
import os
import re
import datetime
import json
import random

import boto3
from openai import OpenAI
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

def handle_event_bridge_trigger(event, context):
    logger.info("handling event bridge trigger")
    logger.debug("instantiating clients")
    events_client = boto3.client('events')
    lambda_client = boto3.client('lambda')
    ai_client = OpenAI()
    slack_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

    # get rule name and ARN from event resources
    if rule_match := re.match(
        pattern=r"^(?P<arn>[\w:\-]+)/(?P<rule_name>[a-zA-Z\-]+)$",
        string=event['resources'][0]
    ):
        gd = rule_match.groupdict()
        rule_name = gd["rule_name"]
    #     if gd["rule_inc"]:
    #         rule_inc = int(gd["rule_inc"])
    #         old_rule_name = f"{rule_name}-{gd['rule_inc']}"
    #     else:
    #         rule_inc = 0
    #         old_rule_name = rule_name
    #     new_rule_inc = rule_inc + 1
    #     new_rule_name = f"{rule_name}-{new_rule_inc}"
    else:
        raise ValueError("Could not get rule ARN and name from event resources")

    # logger.info(
    #     "rule_name: {rule_name}\n"
    #     "rule_inc: {rule_inc}\n"
    #     "old_rule_name: {old_rule_name}\n"
    #     "new_rule_inc: {new_rule_inc}\n"
    #     "new_rule_name: {new_rule_name}"
    # )

    # generate message and send it
    logger.info("getting message from OpenAI")
    completion = ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a piece of workout equipment that is posessed with the damned soul of an evil fitness coach. "
                    "You are maniacally obsessed with making everyone physically fit beyond conventional human limits. "
                    "You terrorize people into exercising through intimidation, fear, and oddly specific threats. You "
                    "never engage in body-shaming or use body-shaming language. Keep your responses relatively short "
                    "and to the point. Do not exceed 280 characters."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Give me a random tip or fact related to fitness, exercising, or nutrition that is not common "
                    "knowledge. Use emojis to make it more engaging."
                )
            },
        ],
        temperature=1.0,
    )

    channel_id = _get_channel_id_by_name(slack_client, "testbots")
    if channel_id is None:
        raise ValueError("Could not find channel ID for 'exercise'")

    logger.info(f"sending message to slack channel {channel_id}")
    response = slack_client.chat_postMessage(
        channel=channel_id,
        text=completion.choices[0].message.content,
    )

    if response['ok']:
        logger.info('Message sent successfully')
    else:
        logger.error('Failed to send message')


    # Remove permission associated with old rule
    # permissions_response = lambda_client.get_policy(FunctionName=context.function_name)
    # found = False
    # if "Policy" in permissions_response:
    #     policy = json.loads(permissions_response["Policy"])
    #     statements = policy.get("Statement", [])
    #     for statement in statements:
    #         if statement["Sid"] == f"{old_rule_name}-permission":
    #             found = True
    #             logger.info(
    #                 f"Removing permission associated with old rule FunctionName: {context.function_name}, StatementId: "
    #                 f"{old_rule_name}-permission"
    #             )
    #             lambda_client.remove_permission(
    #                 FunctionName=context.function_name,
    #                 StatementId=f"{old_rule_name}-permission",
    #             )
    # if not found:
    #     logger.warning("No policy found for function")

    # # Delete existing rule
    # logger.info("Deleting existing EventBridge rule")
    # targets_response = events_client.list_targets_by_rule(Rule=old_rule_name)
    # target_ids = [target['Id'] for target in targets_response['Targets']]
    # if target_ids:
    #     logger.info(f"Removing targets from rule Rule: {old_rule_name}, Ids: {target_ids}")
    #     events_client.remove_targets(
    #         Rule=old_rule_name,
    #         Ids=target_ids,
    #     )
    # else:
    #     logger.warning("No targets found for rule")
    # events_client.delete_rule(Name=old_rule_name)

    # create new EventBridge rule
    logger.info("creating new EventBridge rule")
    #next_trigger_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=5 + random.randint(-2, 2))
    next_trigger_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=20 + random.randint(-10, 10))
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

    # events_client.put_rule(
    #     Name=new_rule_name,
    #     ScheduleExpression=cron_expression,
    #     State="ENABLED",
    # )

    # lambda_client.add_permission(
    #     FunctionName=context.function_name,
    #     StatementId=f"{new_rule_name}-permission",
    #     Action="lambda:InvokeFunction",
    #     Principal="events.amazonaws.com",
    #     SourceArn=f"arn:aws:events:{os.environ['AWS_REGION']}:{os.environ['AWS_ACCOUNT_ID']}:rule/{new_rule_name}",
    # )

    # events_client.put_targets(
    #     Rule=new_rule_name,
    #     Targets=[
    #         {
    #             'Id': 'slackbot_target',
    #             'Arn': context.invoked_function_arn,
    #         }
    #     ]
    # )

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