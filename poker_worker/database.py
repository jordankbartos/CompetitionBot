import boto3
import os
import logging
import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

def to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(i) for i in obj]
    return obj

class PokerDatabase:
    def __init__(self):
        endpoint_url = os.environ.get("DYNAMODB_URL")
        # For local DynamoDB, we must provide a region_name if not in env
        region_name = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        
        if endpoint_url:
            self.dynamodb = boto3.resource(
                "dynamodb", 
                endpoint_url=endpoint_url, 
                region_name=region_name,
                aws_access_key_id="local",
                aws_secret_access_key="local"
            )
        else:
            self.dynamodb = boto3.resource("dynamodb")
            
        self.table_name = os.environ["DYNAMODB_TABLE"]
        self.table = self.dynamodb.Table(self.table_name)

    def register_user(self, slack_id, poker_name, venmo_handle):
        try:
            self.table.put_item(
                Item={
                    "PK": f"USER#{slack_id}",
                    "SK": "PROFILE",
                    "poker_name": poker_name,
                    "venmo_handle": venmo_handle
                }
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to register user {slack_id}")
            return False

    def get_user_by_slack_id(self, slack_id):
        try:
            response = self.table.get_item(
                Key={"PK": f"USER#{slack_id}", "SK": "PROFILE"}
            )
            return response.get("Item")
        except Exception as e:
            logger.exception(f"Failed to get user {slack_id}")
            return None

    def get_all_users(self):
        try:
            response = self.table.scan(
                FilterExpression="begins_with(PK, :u) AND SK = :s",
                ExpressionAttributeValues={":u": "USER#", ":s": "PROFILE"}
            )
            return response.get("Items", [])
        except Exception as e:
            logger.exception("Failed to scan users")
            return []

    def save_game(self, game_id, player_data, fingerprint, uploader_id):
        """Stores a game record and updates player stats."""
        now = datetime.datetime.utcnow().isoformat()
        try:
            # Save game record
            self.table.put_item(
                Item=to_decimal({
                    "PK": f"GAME#{game_id}",
                    "SK": "RESULT",
                    "player_data": player_data,
                    "fingerprint": fingerprint,
                    "uploader_id": uploader_id,
                    "timestamp": now
                })
            )
            # Update individual player stats (simplified for now: store history)
            for player_name, net in player_data.items():
                # We'll store a history entry for each player to make leaderboard calculation easier
                # In a high-traffic app we'd use atomic counters, but for this, history is better for auditing
                self.table.put_item(
                    Item=to_decimal({
                        "PK": f"STATS#{player_name.lower().strip()}",
                        "SK": f"GAME#{game_id}",
                        "net_amount": net,
                        "timestamp": now
                    })
                )
            return True
        except Exception as e:
            logger.exception(f"Failed to save game {game_id}")
            return False

    def get_recent_games(self, limit=5):
        try:
            # This is a bit inefficient with Scan, but fine for a small group
            # Ideally we'd have a GSI on SK and timestamp
            response = self.table.scan(
                FilterExpression="SK = :s",
                ExpressionAttributeValues={":s": "RESULT"}
            )
            items = response.get("Items", [])
            items.sort(key=lambda x: x['timestamp'], reverse=True)
            return items[:limit]
        except Exception as e:
            logger.exception("Failed to get recent games")
            return []

    def get_leaderboard(self):
        try:
            response = self.table.scan(
                FilterExpression="begins_with(PK, :p)",
                ExpressionAttributeValues={":p": "STATS#"}
            )
            items = response.get("Items", [])
            totals = {}
            for item in items:
                name = item['PK'].replace('STATS#', '')
                amount = float(item['net_amount'])
                totals[name] = totals.get(name, 0) + amount
            
            sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)
            return sorted_totals
        except Exception as e:
            logger.exception("Failed to get leaderboard")
            return []

    def save_poll_metadata(self, week_id, channel_id, message_ts, emoji_mapping):
        """
        Stores metadata for the weekly poll.
        PK: POLL#<week_id>, SK: METADATA
        """
        try:
            self.table.put_item(
                Item={
                    "PK": f"POLL#{week_id}",
                    "SK": "METADATA",
                    "channel_id": channel_id,
                    "message_ts": message_ts,
                    "emoji_mapping": emoji_mapping  # Map of emoji_name -> Day (e.g., {"billnye": "Mon"})
                }
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to save poll metadata for {week_id}")
            return False

    def get_poll_metadata(self, week_id):
        try:
            response = self.table.get_item(
                Key={
                    "PK": f"POLL#{week_id}",
                    "SK": "METADATA"
                }
            )
            return response.get("Item")
        except Exception as e:
            logger.exception(f"Failed to get poll metadata for {week_id}")
            return None

    def get_poll(self, week_id):
        try:
            response = self.table.get_item(
                Key={
                    "PK": f"POLL#{week_id}",
                    "SK": "VOTES"
                }
            )
            return response.get("Item")
        except Exception as e:
            logger.exception(f"Failed to get poll {week_id}")
            return None
