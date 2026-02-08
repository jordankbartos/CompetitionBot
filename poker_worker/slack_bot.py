import json
import logging
import os
import re
import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import google.generativeai as genai
from google.generativeai import types

from database import PokerDatabase
from vision import download_slack_image, process_poker_screenshot
from settlement import calculate_settlements, generate_venmo_link
from config import SYSTEM_PROMPT, VISION_PROMPT, MODEL_NAME
from event_bridge_trigger import handle_event_bridge_trigger
from utils import get_env
import agent_tools

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

# Configure Gemini once at startup
google_api_key = get_env("GOOGLE_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)

slack_token = get_env('SLACK_BOT_TOKEN')
client = WebClient(token=slack_token)

# Get Bot User ID dynamically
try:
    bot_user_id = client.auth_test()["user_id"]
    logger.info(f"Authenticated as bot user: {bot_user_id}")
except Exception as e:
    logger.error(f"Failed to authenticate with Slack: {e}")
    bot_user_id = "U07D8V4D145" # Fallback

db = PokerDatabase()

# Define the tools for the agent
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

def handle_agentic_conversation(event_data):
    text = event_data.get('text', '')
    channel = event_data.get('channel')
    user_id = event_data.get('user')
    ts = event_data.get('ts')
    thread_ts = event_data.get('thread_ts')

    logger.info(f"Processing message:\n  {channel=}\n  {user_id=}\n  {ts=}\n  {thread_ts=}")
    # 1. Download image if present
    image_bytes = None
    files = event_data.get('files', [])
    if files:
        file_url = files[0].get('url_private')
        image_bytes = download_slack_image(file_url, slack_token)
        if image_bytes:
            # Add a reaction to show we're working
            try:
                client.reactions_add(channel=channel, timestamp=ts, name="eyes")
            except: pass

    # 2. Extract data if image is present
    vision_data = None
    if image_bytes:
        vision_json = process_poker_screenshot(image_bytes)
        if vision_json:
            try:
                vision_data = json.loads(vision_json)
                if 'players' in vision_data:
                    cleaned_players = {}
                    for p, val in vision_data['players'].items():
                        # Remove parenthetical notes like (left) or (host)
                        clean_name = re.sub(r'\(.*?\)', '', p).strip()
                        # ALWAYS treat numbers from vision as cents and convert to dollars
                        amount = float(val) / 100.0
                        # Sum up if the same player appears twice (e.g. once with (left))
                        cleaned_players[clean_name] = cleaned_players.get(clean_name, 0.0) + amount
                    vision_data['players'] = cleaned_players
            except:
                logger.error(f"Failed to parse vision JSON: {vision_json}")

    # 3. Initialize Agent
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT,
        tools=available_tools
    )
    
    # Construct the prompt
    prompt_context = (
        f"Context: channel_id={channel}, thread_ts={thread_ts or 'None'}\n"
        f"User <@{user_id}> says: {text}\n"
    )
    if vision_data:
        formatted_results = [{"name": k, "amount": v} for k, v in vision_data.get('players', {}).items()]
        prompt_context += f"I have extracted the following from the attached screenshot (in dollars): {json.dumps(formatted_results)}\n"
        prompt_context += "If this data is correct and the user wants to settle/record, use the tools to do so."

    chat = model.start_chat(enable_automatic_function_calling=True)
    
    try:
        response = chat.send_message(prompt_context)
        final_text = response.text
        
        # Post the response - Default to channel, not thread
        # We only use thread_ts if the user's message was ALREADY in a thread
        reply_ts = event_data.get('thread_ts')
        
        client.chat_postMessage(channel=channel, text=final_text, thread_ts=reply_ts)
        
    except Exception as e:
        logger.exception("Agent conversation failed")
        client.chat_postMessage(channel=channel, text=f"Sorry, I ran into an error processing that.", thread_ts=ts)

def lambda_handler(event, context):
    logger.info(f"Event: {event}")
    
    if event.get('source') == 'aws.events':
        return handle_event_bridge_trigger(event, context)
    
    payload = event.get('payload')
    payload_type = event.get('type')
    
    if payload_type == "interactive":
        pass
    elif payload_type == "event":
        handle_event(payload)
    
    return {"statusCode": 200, "body": "OK"}

def handle_event(body):
    if 'event' not in body:
        return
    
    event_data = body['event']
    event_type = event_data.get('type')
    user_id = event_data.get('user')
    ts = event_data.get('ts')
    
    # 1. Identity Guard: Never respond to self or other bots
    if user_id == bot_user_id or event_data.get('subtype') == 'bot_message':
        return

    is_mention = False
    text = event_data.get('text', '')
    
    # 2. Check for explicit mention
    # If it's an app_mention, we always process it.
    if event_type == 'app_mention':
        is_mention = True
    
    # 3. If it's a message, check if it's a threaded reply
    elif event_type == 'message' and not event_data.get('subtype'):
        # If the bot is mentioned in a regular message event, Slack ALREADY 
        # sent an app_mention event. We ignore it here to avoid duplicates.
        if f'<@{bot_user_id}>' in text:
            logger.info("Ignoring bot mention in message event (app_mention handles it)")
            return

        thread_ts = event_data.get('thread_ts')
        channel = event_data.get('channel')
        
        if thread_ts:
            # It's a reply in a thread. Check if we are already in it.
            if agent_tools.is_bot_in_thread(channel, thread_ts):
                logger.info(f"Bot participation detected in thread {thread_ts}. Responding...")
                is_mention = True

    if is_mention:
        logger.info(f"Processing {event_type} from {user_id} in channel {event_data.get('channel')}")
        handle_agentic_conversation(event_data)
