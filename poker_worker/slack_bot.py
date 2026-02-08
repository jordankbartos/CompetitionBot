"""
Main orchestrator for the Poker Bot worker.
Handles Slack events, manages agent conversations, and coordinates tools.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import google.generativeai as genai

from database import PokerDatabase
from vision import download_slack_image, process_poker_screenshot
from config import SYSTEM_PROMPT, MODEL_NAME
from event_bridge_trigger import handle_event_bridge_trigger
from utils import get_env
import agent_tools

# Logging configuration
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# Core instances
google_api_key = get_env("GOOGLE_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)

slack_token = get_env('SLACK_BOT_TOKEN') or ""
client = WebClient(token=slack_token)
db = PokerDatabase()

# Identify bot user ID for message filtering
try:
    bot_user_id = client.auth_test()["user_id"]
    logger.info(f"Authenticated as bot user: {bot_user_id}")
except Exception as e:
    logger.error(f"Failed to authenticate with Slack: {e}")
    bot_user_id = "U07D8V4D145"  # Fallback

# Define the tools available to the AI agent
available_tools = [
    agent_tools.get_user_profile,
    agent_tools.register_player,
    agent_tools.calculate_poker_settlements,
    agent_tools.record_game_result,
    agent_tools.get_leaderboard,
    agent_tools.slack_get_history,
    agent_tools.slack_react,
    agent_tools.get_weekly_poll_results
]

def handle_agentic_conversation(event_data: Dict[str, Any]) -> None:
    """
    Manages a multi-step conversation with the Gemini agent.
    Processes images if present and uses tools to fulfill user requests.
    """
    text = event_data.get('text', '')
    channel = event_data.get('channel', '')
    user_id = event_data.get('user', '')
    ts = event_data.get('ts', '')
    thread_ts = event_data.get('thread_ts')

    logger.info(f"Processing message from {user_id} in {channel}")

    # 1. Image Processing (Vision)
    vision_data = None
    files = event_data.get('files', [])
    if files:
        file_url = files[0].get('url_private', '')
        image_bytes = download_slack_image(file_url, slack_token)
        if image_bytes:
            # Signal processing with a reaction
            try:
                client.reactions_add(channel=channel, timestamp=ts, name="eyes")
            except SlackApiError:
                pass
            
            extracted_data = process_poker_screenshot(image_bytes)
            if extracted_data:
                vision_data = _normalize_vision_results(extracted_data)

    # 2. Agent Orchestration
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT,
        tools=available_tools
    )
    
    prompt = _construct_agent_prompt(user_id, text, channel, thread_ts, vision_data)
    chat = model.start_chat(enable_automatic_function_calling=True)
    
    try:
        response = chat.send_message(prompt)
        # Slack replies should usually stay in the same thread if one exists
        reply_ts = thread_ts if thread_ts else None
        client.chat_postMessage(channel=channel, text=response.text, thread_ts=reply_ts)
    except Exception:
        logger.exception("Agent conversation failed")
        client.chat_postMessage(
            channel=channel, 
            text="Sorry, I ran into an error processing that request.", 
            thread_ts=ts
        )

def _normalize_vision_results(data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to clean and normalize results from the Vision API."""
    if 'players' in data:
        cleaned_players = {}
        for p, val in data['players'].items():
            # Normalize names and convert cents to dollars
            clean_name = re.sub(r'\(.*?\)', '', p).strip()
            # Handle potential string amounts from vision
            amount = float(val) / 100.0
            cleaned_players[clean_name] = cleaned_players.get(clean_name, 0.0) + amount
        data['players'] = cleaned_players
    return data

def _construct_agent_prompt(
    user_id: str, 
    text: str, 
    channel: str, 
    thread_ts: Optional[str], 
    vision_data: Optional[Dict[str, Any]]
) -> str:
    """Builds the contextual prompt for the agent."""
    prompt = (
        f"Context: channel_id={channel}, thread_ts={thread_ts or 'None'}\n"
        f"User <@{user_id}> says: {text}\n"
    )
    if vision_data:
        players = vision_data.get('players', {})
        formatted_results = [{"name": k, "amount": v} for k, v in players.items()]
        prompt += f"\nI have extracted the following from the attached screenshot (in dollars): {json.dumps(formatted_results)}\n"
        prompt += "If this data is correct and the user wants to settle or record the results, use the tools to do so."
    return prompt

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main entry point for AWS Lambda.
    Routes EventBridge triggers and Slack payloads.
    """
    logger.info(f"Received Lambda event: {json.dumps(event)}")
    
    # Handle EventBridge (Scheduled tasks)
    if event.get('source') == 'aws.events':
        return handle_event_bridge_trigger(event, context)
    
    # Handle Slack Dispatch
    payload = event.get('payload')
    payload_type = event.get('type')
    
    if payload_type == "event" and isinstance(payload, dict):
        handle_event(payload)
    
    return {"statusCode": 200, "body": "OK"}

def handle_event(body: Dict[str, Any]) -> None:
    """Determines if the bot should respond to a given Slack event."""
    if 'event' not in body:
        return
    
    event_data = body['event']
    event_type = event_data.get('type')
    user_id = event_data.get('user')
    text = event_data.get('text', '')
    
    # Ignore self and other bots
    if user_id == bot_user_id or event_data.get('subtype') == 'bot_message':
        return

    should_respond = False
    
    # Always respond to direct mentions
    if event_type == 'app_mention':
        should_respond = True
    
    # Respond to messages in threads where the bot is already participating
    elif event_type == 'message' and not event_data.get('subtype'):
        # Slack sends both app_mention and message for mentions; ignore the duplicate
        if f'<@{bot_user_id}>' in text:
            return

        thread_ts = event_data.get('thread_ts')
        channel = event_data.get('channel', '')
        if thread_ts and agent_tools.is_bot_in_thread(channel, thread_ts):
            logger.info(f"Continuing conversation in thread {thread_ts}")
            should_respond = True

    if should_respond:
        handle_agentic_conversation(event_data)
