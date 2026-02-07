import json
import logging
import os
import re
import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import google.generativeai as genai

from database import PokerDatabase
from vision import download_slack_image, process_poker_screenshot
from settlement import calculate_settlements, generate_venmo_link
from config import SYSTEM_PROMPT, VISION_PROMPT
from event_bridge_trigger import handle_event_bridge_trigger

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
logger.setLevel(log_level)

slack_token = os.environ['SLACK_BOT_TOKEN']
client = WebClient(token=slack_token)
db = PokerDatabase()

def lambda_handler(event, context):
    logger.info(f"Event: {event}")
    
    if event.get('source') == 'aws.events':
        return handle_event_bridge_trigger(event, context)
    
    payload = event.get('payload')
    payload_type = event.get('type')
    
    if payload_type == "interactive":
        handle_interactive(payload)
    elif payload_type == "event":
        handle_event(payload)
    
    return {"statusCode": 200, "body": "OK"}

def handle_interactive(payload):
    user_id = payload['user']['id']
    actions = payload.get('actions', [])
    if not actions:
        return

    action = actions[0]
    action_id = action['action_id']
    
    if action_id.startswith("poll_vote_"):
        day = action_id.replace("poll_vote_", "")
        week_id = datetime.datetime.now().strftime("%Y-W%V")
        success = db.save_poll_vote(week_id, day, user_id)
        if success:
            logger.info(f"Vote saved for {user_id}: {day}")

def handle_event(body):
    if 'event' not in body:
        return
    
    event_data = body['event']
    if event_data.get('type') == 'app_mention' and 'subtype' not in event_data:
        text = event_data.get('text', '').lower()
        channel = event_data.get('channel')
        user_id = event_data.get('user')
        
        if "register" in text:
            handle_registration(text, user_id, channel)
        elif "settle up" in text:
            handle_settlement(event_data, channel)
        elif "results" in text or "poll" in text:
            handle_poll_results(channel)
        else:
            handle_conversation(event_data, channel)

def handle_poll_results(channel):
    week_id = datetime.datetime.now().strftime("%Y-W%V")
    poll_data = db.get_poll(week_id)
    
    if not poll_data or not poll_data.get('votes'):
        client.chat_postMessage(channel=channel, text=f"No votes yet for this week ({week_id})!")
        return

    # votes is a map: user_id -> day
    votes = poll_data['votes']
    tally = {}
    for uid, day in votes.items():
        tally[day] = tally.get(day, 0) + 1
    
    sorted_days = sorted(tally.items(), key=lambda x: x[1], reverse=True)
    
    response = [f"*Poll Results for week {week_id}:*"]
    for day, count in sorted_days:
        response.append(f"• {day}: {count} vote(s)")
    
    client.chat_postMessage(channel=channel, text="\n".join(response))

def handle_registration(text, slack_id, channel):
    match = re.search(r'register\s+"([^"]+)"\s+(@?[\w-]+)', text, re.IGNORECASE)
    if match:
        poker_name = match.group(1)
        venmo_handle = match.group(2)
        if not venmo_handle.startswith('@'):
            venmo_handle = '@' + venmo_handle
            
        success = db.register_user(slack_id, poker_name, venmo_handle)
        if success:
            msg = f"Got it! I've registered <@{slack_id}> as '{poker_name}' with Venmo handle {venmo_handle}."
        else:
            msg = "Sorry, I had trouble saving your registration. Try again later?"
    else:
        msg = "To register, use: `@PokerBot register \"Your Poker Name\" @YourVenmoHandle`"
    
    client.chat_postMessage(channel=channel, text=msg)

def handle_settlement(event_data, channel):
    files = event_data.get('files', [])
    if not files:
        client.chat_postMessage(channel=channel, text="Please attach the Pokerrrr 2 screenshot to your 'settle up' message!")
        return

    client.chat_postMessage(channel=channel, text="Processing the screenshot... give me a second.")
    
    file_url = files[0].get('url_private')
    image_content = download_slack_image(file_url, slack_token)
    
    if not image_content:
        client.chat_postMessage(channel=channel, text="I couldn't download the image. Make sure I have permission to see files!")
        return
    
    vision_json = process_poker_screenshot(image_content)
    if not vision_json:
        client.chat_postMessage(channel=channel, text="I couldn't read the screenshot. Is it a clear Pokerrrr 2 result screen?")
        return
    
    try:
        player_data = json.loads(vision_json)
        
        # Validation: Sum should be 0
        total_sum = sum(player_data.values())
        if abs(total_sum) > 0.01: # Use small epsilon for float issues
            client.chat_postMessage(channel=channel, text=f"Warning: The net amounts extracted don't sum to zero (Total: {total_sum}). Please check the data or provide a clearer screenshot.")
            # We'll still show the data so they can see where it went wrong
            client.chat_postMessage(channel=channel, text=f"Extracted data: {json.dumps(player_data, indent=2)}")
            return

        settlements = calculate_settlements(player_data)
        if not settlements:
            client.chat_postMessage(channel=channel, text="Looks like everyone is even! Nothing to settle.")
            return
            
        users = db.get_all_users()
        poker_to_venmo = {u['poker_name']: u['venmo_handle'] for u in users}
        poker_to_slack = {u['poker_name']: u['PK'].replace('USER#', '') for u in users}
        
        response_lines = ["*Settlement Plan:*"]
        for debtor_poker, creditor_poker, amount in settlements:
            creditor_venmo = poker_to_venmo.get(creditor_poker, f"(No Venmo for {creditor_poker})")
            debtor_slack = poker_to_slack.get(debtor_poker)
            debtor_tag = f"<@{debtor_slack}>" if debtor_slack else debtor_poker
            
            v_link = generate_venmo_link(creditor_venmo, amount) if "No Venmo" not in creditor_venmo else ""
            link_text = f"<{v_link}|Pay {creditor_venmo}>" if v_link else "Please register to get Venmo links!"
            
            response_lines.append(f"• {debtor_tag} pays *{creditor_poker}* ${amount:.2f} - {link_text}")
            
        client.chat_postMessage(channel=channel, text="\n".join(response_lines))
        
    except Exception as e:
        logger.exception("Settlement calculation failed")
        client.chat_postMessage(channel=channel, text="I ran into an error calculating the settlements. Check the logs!")

def handle_conversation(event_data, channel):
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)
    
    response = model.generate_content(event_data.get('text', ''))
    client.chat_postMessage(channel=channel, text=response.text)
