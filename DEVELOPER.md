# Developer Guide

This document explains how to set up the local development environment for PokerBot, including E2E testing with Slack.

## Local Development Stack

- **Database:** DynamoDB Local (via Docker Compose)
- **AI:** Google Gemini (Live API)
- **Slack Tunnel:** ngrok (to receive webhooks locally)
- **Bridge:** Flask (to translate Slack HTTP requests to Lambda events)

## Prerequisites

1.  **Docker & Docker Compose**
2.  **AWS CLI** (configured with `compbot-dev` profile)
3.  **Python 3.12** (managed via Conda)
4.  **ngrok** (If using the containerized tunnel, you need an authtoken)

## Local Setup Instructions (Full Containerized)

### 0. Environment Setup
The development environment is managed with **Conda**.
- **Environment Name:** `slackbot`
- **Python Version:** 3.12

Before beginning development, verify that this environment exists and is active:
```bash
conda activate slackbot
python --version  # Should be 3.12.x
```

### 1. Configure Environment Variables
Generate your `.env` file by pulling secrets from AWS Secrets Manager:
```bash
# This requires AWS CLI login with the compbot-dev profile
./scripts/fetch_secrets.sh
```
*Note: If you want to use ngrok in the container, manually add `NGROK_AUTHTOKEN=your_token` to the generated `.env` file.*

### 2. Start the Stack
```bash
docker-compose up --build
```
This single command will:
- Start **DynamoDB Local**.
- **Initialize** the local table schema.
- Start the **Slack Bridge** (Flask server) on port 5000.
- Start **ngrok** (if authtoken is provided).

### 3. Update Slack App Configuration
Go to your [Slack App Dashboard](https://api.slack.com/apps):
- **Event Subscriptions:** Change Request URL to your ngrok URL + `/slackbot`.
- **Interactivity & Shortcuts:** Change Request URL to your ngrok URL + `/slackbot`.

*Note: The production URL for this app is:* `https://ofl4z9e8u9.execute-api.us-east-1.amazonaws.com/prod/slackbot`

## Legacy/Manual Local Setup (Host-side)
If you prefer running the bridge directly in your host environment (e.g., for easier debugging in an IDE):

1.  **Start DB:** `docker-compose up -d dynamodb-local`
2.  **Env Variables:** Since the script now generates a `.env` file, you can load it into your shell using:
    ```bash
    export $(grep -v '^#' .env | xargs)
    ```
3.  **Init DB:** `python scripts/init_local_db.py`
4.  **Run Bridge:** `python local_bridge.py`
5.  **ngrok:** `ngrok http 5000`

## Build and Deployment

### Binary Compatibility
AWS Lambda runs on Amazon Linux. If you are developing on a different OS (e.g., Manjaro, MacOS), `pip install` may download incompatible binary extensions.

**Always use `build.sh` to package the app.** It uses a Dockerized Amazon Linux environment to ensure compatibility.

### Deployment Workflow
1.  Verify changes locally via the bridge.
2.  Run `./build.sh` to create the zip files.
3.  Run `./deploy.sh` to apply infrastructure changes and update code.
4.  Revert Slack App URLs back to the production API Gateway endpoint.
