import os
import json
import hmac
import hashlib
import time
import sys
from flask import Flask, request, jsonify

# Add poker_worker to path so we can import the handler
sys.path.append(os.path.join(os.getcwd(), "poker_worker"))
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
    timestamp = headers.get('x-slack-request-timestamp')
    signature = headers.get('x-slack-signature')

    if not timestamp or not signature:
        print(f"Missing headers: timestamp={timestamp}, signature={signature}")
        return False

    # Create the base string using bytes to be 100% safe
    sig_basestring = b"v0:" + timestamp.encode('utf-8') + b":" + raw_body_bytes
    
    my_signature = 'v0=' + hmac.new(
        actual_secret.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()

    verified = hmac.compare_digest(my_signature, signature)
    if not verified:
        print(f"Signature mismatch!")
        print(f"  Generated: {my_signature}")
        print(f"  Received:  {signature}")
        print(f"  BaseString: {sig_basestring.decode('utf-8', errors='replace')}")
    return verified

@app.route("/slackbot", methods=["POST"])
def slackbot():
    raw_body_bytes = request.get_data()
    # Normalize headers to lowercase for easy lookup
    headers = {k.lower(): v for k, v in request.headers.items()}
    
    print(f"\n--- Incoming request to /slackbot ---")
    
    if not verify_slack_signature(headers, raw_body_bytes):
        return "Forbidden", 403

    body = request.get_json(silent=True) or {}
    payload_type = "event"
    
    # Check for interactive payload
    content_type = headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        # Flask handles form data in request.form
        if 'payload' in request.form:
            body = json.loads(request.form['payload'])
            payload_type = "interactive"

    print(f"Payload Type: {payload_type}")
    print(f"Body: {json.dumps(body, indent=2)}")

    # Handle Slack URL verification challenge
    if body and 'challenge' in body:
        print("Responding to Slack challenge")
        return body['challenge'], 200, {'Content-Type': 'text/plain'}

    # Invoke the worker handler directly
    event = {
        "payload": body,
        "type": payload_type
    }
    
    # Run the handler (in a real Lambda this would be async, but here we run it sync for simplicity)
    # If it takes too long Slack might timeout (3s), but for local testing it's usually fine.
    try:
        lambda_handler(event, None)
    except Exception as e:
        print(f"Error in lambda_handler: {e}")

    return "OK", 200

if __name__ == "__main__":
    # Check if .env exists
    if not os.path.exists(".env"):
        print("ERROR: .env file not found!")
        print("Please run ./scripts/fetch_secrets.sh to generate it from AWS Secrets Manager.")
        sys.exit(1)

    # Ensure necessary env vars are present
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "GOOGLE_API_KEY", "DYNAMODB_TABLE"]
    for var in required_vars:
        if not os.environ.get(var):
            print(f"WARNING: {var} is not set!")

    app.run(host="0.0.0.0", port=5000, debug=True)
