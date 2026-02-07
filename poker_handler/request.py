import os
import logging
import json
import boto3
import urllib.parse
import hmac
import hashlib
import time

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

worker_function = os.environ.get("WORKER_FUNCTION_NAME", "poker_worker")
signing_secret = os.environ.get("SLACK_SIGNING_SECRET")

def verify_slack_signature(headers, raw_body):
    if not signing_secret:
        logger.warning("SLACK_SIGNING_SECRET not set, skipping verification")
        return True

    timestamp = headers.get('X-Slack-Request-Timestamp')
    signature = headers.get('X-Slack-Signature')

    if not timestamp or not signature:
        return False

    # Prevent replay attacks
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{raw_body}".encode('utf-8')
    my_signature = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, signature)

def request_handler(event, context):
    logger.info(f"Event: {event}")
    
    headers = {k.lower(): v for k, v in event.get('headers', {}).items()} # Case-insensitive
    
    # Slack retry logic: Ignore retries to avoid duplicates during long-running tasks
    if headers.get('x-slack-retry-num'):
        logger.info(f"Ignoring Slack retry attempt {headers.get('x-slack-retry-num')}")
        return {
            'statusCode': 200,
            'body': json.dumps('Success (Retry Ignored)')
        }

    raw_body = event.get('body', '')
    if not raw_body:
        return {'statusCode': 400, 'body': 'Empty body'}

    if not verify_slack_signature(headers, raw_body):
        logger.error("Invalid slack signature")
        return {'statusCode': 403, 'body': 'Forbidden'}

    body_str = raw_body
    # Check if it's a URL-encoded payload (from interactive components)
    if event.get('isBase64Encoded'):
        import base64
        body_str = base64.b64decode(body_str).decode('utf-8')
    
    if body_str.startswith('payload='):
        # Interactive component payload
        decoded_body = urllib.parse.unquote_plus(body_str[8:])
        body = json.loads(decoded_body)
        payload_type = "interactive"
    else:
        try:
            body = json.loads(body_str)
            payload_type = "event"
        except json.JSONDecodeError:
            return {'statusCode': 400, 'body': 'Invalid JSON'}

    # Handle Challenge
    if 'challenge' in body:
        return {
            'statusCode': 200,
            'body': json.dumps(body['challenge'])
        }

    # Forward to worker
    try:
        logger.info(f"Forwarding {payload_type} to worker lambda")
        lambda_client = boto3.client('lambda')
        response = lambda_client.invoke(
            FunctionName=worker_function,
            InvocationType="Event",
            Payload=json.dumps(dict(
                payload=body,
                type=payload_type
            ))
        )
        logger.info(f"Worker invoked: {response}")
    except Exception as e:
        logger.exception("Error invoking worker Lambda")

    return {
        'statusCode': 200,
        'body': json.dumps('Success')
    }
