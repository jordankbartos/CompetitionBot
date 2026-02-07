import boto3
import os
import logging

logger = logging.getLogger(__name__)

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
