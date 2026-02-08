import base64
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse

import boto3

from utils import get_secret

# Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

try:
    WORKER_FUNCTION = get_secret("WORKER_FUNCTION_NAME")
    SIGNING_SECRET = get_secret("SLACK_SIGNING_SECRET")
except ValueError as e:
    logger.error(f"Initialization error: {e}")
    # We don't crash here so Lambda logs can still be viewed, but handler will fail
    WORKER_FUNCTION = None
    SIGNING_SECRET = None


def request_handler(event, context):
    """
    API Gateway entry point. Validates Slack requests and forwards them
    to a background worker to avoid Slack's 3-second timeout.
    """
    logger.debug(f"Received event: {json.dumps(event)}")
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}

    # 1. Early Exit: Ignore Slack Retries
    if retry := headers.get("x-slack-retry-num"):
        logger.info(f"Ignoring Slack retry attempt {retry}")
        return {"statusCode": 200, "body": "Retry ignored"}

    # 2. Decode Body for Validation
    body_str = event.get("body", "")
    if event.get("isBase64Encoded"):
        try:
            body_str = base64.b64decode(body_str).decode("utf-8")
        except Exception:
            return {"statusCode": 400, "body": "Invalid encoding"}

    # 3. Security Check: Signature Verification
    if not _verify_slack_signature(headers, body_str):
        return {"statusCode": 403, "body": "Forbidden"}

    # 4. Parse Payload
    payload, payload_type = _extract_payload(body_str)
    if not payload:
        return {"statusCode": 400, "body": "Malformed request"}

    # 5. Handle URL Verification Challenge
    if payload.get("type") == "url_verification":
        return {"statusCode": 200, "body": payload.get("challenge")}

    # 6. Dispatch to Background Worker
    _forward_to_worker(payload, payload_type)

    return {
        "statusCode": 200,
        "body": json.dumps({"status": "success", "message": "Payload forwarded"}),
    }


def _verify_slack_signature(headers, body_str):
    """Verify the HMAC signature provided by Slack."""
    if not SIGNING_SECRET:
        logger.error("SLACK_SIGNING_SECRET not configured")
        return False

    timestamp = headers.get("x-slack-request-timestamp")
    signature = headers.get("x-slack-signature")

    if not timestamp or not signature:
        logger.error("Missing Slack signature headers")
        return False

    # Prevent replay attacks
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            logger.error("Slack request timestamp outside valid window")
            return False
    except (ValueError, TypeError):
        logger.error(f"Invalid timestamp format: {timestamp}")
        return False

    sig_basestring = f"v0:{timestamp}:{body_str}".encode("utf-8")
    computed = (
        "v0=" + hmac.new(SIGNING_SECRET.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()
    )

    if not hmac.compare_digest(computed, signature):
        logger.error(f"Signature mismatch. Received: {signature}")
        return False

    return True


def _extract_payload(body_str):
    """
    Parses the body based on Slack's payload type.
    Returns: (dict payload, str payload_type)
    """
    if not body_str:
        return None, None

    # Slack Interactive Components use 'payload=URL_ENCODED_JSON'
    if body_str.startswith("payload="):
        try:
            decoded = urllib.parse.unquote_plus(body_str[len("payload=") :])
            return json.loads(decoded), "interactive"
        except Exception:
            logger.exception("Failed to parse interactive payload")
            return None, None

    # Standard Events use JSON
    try:
        return json.loads(body_str), "event"
    except json.JSONDecodeError:
        logger.debug("Body is not JSON, might be a raw message")
        return None, None


def _forward_to_worker(payload, payload_type):
    """Dispatches the payload to the worker Lambda asynchronously."""
    if not WORKER_FUNCTION:
        logger.error("WORKER_FUNCTION_NAME not configured")
        return

    logger.info(f"Forwarding {payload_type} to worker: {WORKER_FUNCTION}")
    try:
        lambda_client = boto3.client("lambda")
        lambda_client.invoke(
            FunctionName=WORKER_FUNCTION,
            InvocationType="Event",
            Payload=json.dumps({"payload": payload, "type": payload_type}),
        )
    except Exception:
        logger.exception("Error invoking worker Lambda")
