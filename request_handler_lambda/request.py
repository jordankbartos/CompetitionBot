import os
import logging
import json
import boto3

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

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

def request_handler(event, context):

    logger.info(f"Event: {event}")
    logger.info(f"Context: {context}")

    body = json.loads(event.get('body'))

    if not body:
        raise RuntimeError("No event body to process")

    if 'challenge' in body:
        ret = {
            'statusCode': 200,
            'body': json.dumps(body['challenge'])
        }
    elif 'event' in body:

        event_data = body['event']

        if event_data['type'] == 'app_mention' and 'subtype' not in event_data:

            try:
                logger.info("Forwarding to worker lambda")
                lambda_client = boto3.client('lambda')
                response = lambda_client.invoke(
                    FunctionName="worker_slackbot",
                    InvocationType="Event",
                    Payload=json.dumps(dict(
                        original_event=body,
                        additional_data="placeholder",
                    ))
                )
                logger.info(f"Secondary lambda invoked: {response}")
            except Exception as e:
                logger.exception("Error invoking secondary Lambda")

        ret = {
            'statusCode': 200,
            'body': json.dumps('Success')
        }

    return ret