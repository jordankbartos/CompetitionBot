import boto3
import os
import logging

logger = logging.getLogger(__name__)

class PokerDatabase:
    def __init__(self):
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
                Key={
                    "PK": f"USER#{slack_id}",
                    "SK": "PROFILE"
                }
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

    def save_poll_vote(self, week_id, day, slack_id):
        """
        Saves a vote atomically using update_item.
        Structure: POLL#<week_id> / VOTES
        Attribute 'votes' is a Map: { 'Mon': ['user1'], 'Tue': [] }
        """
        try:
            # First, ensure the map and the day list exist
            # We use an empty map if 'votes' doesn't exist, and an empty list if 'day' doesn't exist.
            # However, DynamoDB update expressions for maps of lists are tricky.
            # Simpler for small groups: Use a Set of strings for each day.
            
            # This expression:
            # 1. Ensures 'votes' exists (if not, set to empty map)
            # 2. Ensures 'votes.<day>' exists (if not, set to empty set)
            # 3. Adds the slack_id to the set
            
            # Since we want to ensure 1 vote per person, we first remove them from ALL days.
            # For simplicity in this implementation, we'll do a get-then-update but with 
            # optimistic locking or just accept the minor race risk for "removal".
            # Actually, let's just use a Map: user_id -> day. This is inherently atomic and prevents multi-voting.
            
            self.table.update_item(
                Key={"PK": f"POLL#{week_id}", "SK": "VOTES"},
                UpdateExpression="SET votes.#uid = :day",
                ExpressionAttributeNames={"#uid": slack_id},
                ExpressionAttributeValues={":day": day}
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to save vote for {slack_id}")
            return False

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
