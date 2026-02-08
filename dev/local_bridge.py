import hashlib
import hmac
import json
import os
import sys
import threading

from dotenv import load_dotenv
from flask import Flask, request

# Find project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(PROJECT_ROOT)

# Load .env file from project root
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Add poker_worker to path so we can import the handler
sys.path.append(os.path.join(PROJECT_ROOT, "poker_worker"))

from event_bridge_trigger import handle_event_bridge_trigger
from slack_bot import lambda_handler

from utils import get_env

app = Flask(__name__)

SIGNING_SECRET = get_env("SLACK_SIGNING_SECRET")


def verify_slack_signature(headers, raw_body_bytes):
    if not SIGNING_SECRET:
        print("WARNING: SLACK_SIGNING_SECRET not set, skipping verification")
        return True

    # Use the secret as-is (get_env already handled JSON extraction)
    actual_secret = SIGNING_SECRET

    # Use lowercase keys as we normalized them in the route
    timestamp = headers.get("x-slack-request-timestamp")
    signature = headers.get("x-slack-signature")

    if not timestamp or not signature:
        print(f"Missing headers: timestamp={timestamp}, signature={signature}")
        return False

    # Create the base string using bytes to be 100% safe
    sig_basestring = b"v0:" + timestamp.encode("utf-8") + b":" + raw_body_bytes

    my_signature = (
        "v0=" + hmac.new(actual_secret.encode("utf-8"), sig_basestring, hashlib.sha256).hexdigest()
    )

    verified = hmac.compare_digest(my_signature, signature)
    if not verified:
        print("Signature mismatch!")
        print(f"  Generated: {my_signature}")
        print(f"  Received:  {signature}")
        print(f"  BaseString: {sig_basestring.decode('utf-8', errors='replace')}")
    return verified


@app.route("/slackbot", methods=["POST"])
def slackbot():
    raw_body_bytes = request.get_data()
    # Normalize headers to lowercase for easy lookup
    headers = {k.lower(): v for k, v in request.headers.items()}

    print("\n--- Incoming request to /slackbot ---")

    if not verify_slack_signature(headers, raw_body_bytes):
        return "Forbidden", 403

    # Slack retry logic: Ignore retries to avoid duplicates during long-running tasks
    if headers.get("x-slack-retry-num"):
        print(f"Ignoring Slack retry attempt {headers.get('x-slack-retry-num')}")
        return "OK", 200

    body = request.get_json(silent=True) or {}
    payload_type = "event"

    # Check for interactive payload
    content_type = headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        # Flask handles form data in request.form
        if "payload" in request.form:
            body = json.loads(request.form["payload"])
            payload_type = "interactive"

    print(f"Payload Type: {payload_type}")
    print(f"Body: {json.dumps(body, indent=2)}")

    # Handle Slack URL verification challenge
    if body and "challenge" in body:
        print("Responding to Slack challenge")
        return body["challenge"], 200, {"Content-Type": "text/plain"}

    # Invoke the worker handler in a background thread
    event = {"payload": body, "type": payload_type}

    def run_async():
        try:
            lambda_handler(event, None)
        except Exception as e:
            print(f"Error in lambda_handler: {e}")

    thread = threading.Thread(target=run_async)
    thread.start()

    return "OK", 200


@app.route("/trigger-poll", methods=["POST"])
def trigger_poll():
    print("\n--- Manually triggering weekly poker poll ---")
    event = {"source": "aws.events"}
    try:
        handle_event_bridge_trigger(event, None)
        return "Poll triggered", 200
    except Exception as e:
        print(f"Error triggering poll: {e}")
        return str(e), 500


if __name__ == "__main__":
    # Check if .env exists
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(env_path):
        print(f"ERROR: .env file not found at {env_path}!")
        print("Please run `make secrets` to generate it from AWS Secrets Manager.")
        sys.exit(1)

    # Ensure necessary env vars are present
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "GOOGLE_API_KEY", "DYNAMODB_TABLE"]
    for var in required_vars:
        if not os.environ.get(var):
            print(f"WARNING: {var} is not set!")

    app.run(host="0.0.0.0", port=5000, debug=True)
