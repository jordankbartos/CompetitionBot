#!/bin/bash

# Fetch secrets from AWS Secrets Manager and generate a .env file
# Usage: ./scripts/fetch_secrets.sh

echo "Fetching secrets from AWS using profile: compbot-dev..."

export AWS_PROFILE="compbot-dev"

# Helper function to get secret and parse JSON if necessary
get_secret() {
    local secret_id=$1
    local raw=$(aws secretsmanager get-secret-value --secret-id "$secret_id" --query SecretString --output text)
    # Use python to safely parse JSON or return the raw string
    python3 -c "
import json, sys
data = sys.argv[1]
try:
    obj = json.loads(data)
    if isinstance(obj, dict):
        # Return the first value or a specific key if it matches the secret_id
        key = '$secret_id'
        if key in obj:
            print(obj[key])
        elif key.upper() in obj:
            print(obj[key.upper()])
        else:
            print(list(obj.values())[0])
    else:
        print(data)
except:
    print(data)
" "$raw"
}

SLACK_BOT_TOKEN=$(get_secret "slack_bot_token")
SLACK_SIGNING_SECRET=$(get_secret "slack_signing_secret")
GOOGLE_API_KEY=$(get_secret "GOOGLE_API_KEY")
NGROK_AUTHTOKEN=$(get_secret "NGROK_AUTHTOKEN" 2>/dev/null)
if [ -z "$NGROK_AUTHTOKEN" ]; then
    NGROK_AUTHTOKEN="your-ngrok-token-here"
fi

# Create/Overwrite .env file
cat <<EOF > .env
SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN
SLACK_SIGNING_SECRET=$SLACK_SIGNING_SECRET
GOOGLE_API_KEY=$GOOGLE_API_KEY
NGROK_AUTHTOKEN=$NGROK_AUTHTOKEN
DYNAMODB_TABLE=poker_bot_data
DYNAMODB_URL=http://localhost:8000
EOF

echo ".env file generated successfully."
