"""
Adapter for DynamoDB interaction.
Follows Single-Table Design patterns as defined in AGENTS.md.
"""

import datetime
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from logging_utils import get_logger

logger = get_logger(__name__)


def to_decimal(obj: Any) -> Any:
    """
    Recursively converts float values to Decimal for DynamoDB compatibility.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(i) for i in obj]
    return obj


class PokerDatabase:
    """
    Handles all persistent storage operations for the Poker Bot.
    """

    def __init__(self):
        endpoint_url = os.environ.get("DYNAMODB_URL")
        region_name = os.environ.get(
            "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )

        if endpoint_url:
            self.dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=endpoint_url,
                region_name=region_name,
                aws_access_key_id="local",
                aws_secret_access_key="local",
            )
        else:
            self.dynamodb = boto3.resource("dynamodb")

        self.table_name = os.environ["DYNAMODB_TABLE"]
        self.table = self.dynamodb.Table(self.table_name)

    def register_user(self, slack_id: str, poker_name: str, venmo_handle: str) -> bool:
        """
        Creates or updates a user profile.

        PK: USER#<slack_id>, SK: PROFILE
        """
        try:
            self.table.put_item(
                Item={
                    "PK": f"USER#{slack_id}",
                    "SK": "PROFILE",
                    "poker_name": poker_name,
                    "venmo_handle": venmo_handle,
                    "updated_at": datetime.datetime.utcnow().isoformat(),
                }
            )
            return True
        except ClientError:
            logger.exception(f"Failed to register user {slack_id}")
            return False

    def get_user_by_slack_id(self, slack_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a user's profile information.
        """
        try:
            response = self.table.get_item(Key={"PK": f"USER#{slack_id}", "SK": "PROFILE"})
            return response.get("Item")
        except ClientError:
            logger.exception(f"Failed to get user {slack_id}")
            return None

    def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Retrieves all registered user profiles.
        Note: Uses Scan, which is acceptable for small groups as per AGENTS.md.
        """
        try:
            response = self.table.scan(
                FilterExpression="begins_with(PK, :u) AND SK = :s",
                ExpressionAttributeValues={":u": "USER#", ":s": "PROFILE"},
            )
            return response.get("Items", [])
        except ClientError:
            logger.exception("Failed to scan users")
            return []

    def save_game(
        self, game_id: str, player_data: Dict[str, float], fingerprint: str, uploader_id: str
    ) -> bool:
        """
        Stores a game record and updates individual player stats.

        Game: PK: GAME#<game_id>, SK: RESULT
        Stats: PK: STATS#<lowercase_name>, SK: GAME#<game_id>
        """
        now = datetime.datetime.utcnow().isoformat()
        try:
            # Save game record
            self.table.put_item(
                Item=to_decimal(
                    {
                        "PK": f"GAME#{game_id}",
                        "SK": "RESULT",
                        "player_data": player_data,
                        "fingerprint": fingerprint,
                        "uploader_id": uploader_id,
                        "timestamp": now,
                    }
                )
            )

            # Update individual player stats for auditing and leaderboard calculation
            for player_name, net in player_data.items():
                self.table.put_item(
                    Item=to_decimal(
                        {
                            "PK": f"STATS#{player_name.lower().strip()}",
                            "SK": f"GAME#{game_id}",
                            "net_amount": net,
                            "timestamp": now,
                        }
                    )
                )
            return True
        except ClientError:
            logger.exception(f"Failed to save game {game_id}")
            return False

    def get_recent_games(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the most recent game results.
        """
        try:
            response = self.table.scan(
                FilterExpression="SK = :s", ExpressionAttributeValues={":s": "RESULT"}
            )
            items = response.get("Items", [])
            items.sort(key=lambda x: x["timestamp"], reverse=True)
            return items[:limit]
        except ClientError:
            logger.exception("Failed to get recent games")
            return []

    def get_leaderboard(self) -> List[Tuple[str, float]]:
        """
        Calculates the all-time profit/loss leaderboard from player stats.
        """
        try:
            response = self.table.scan(
                FilterExpression="begins_with(PK, :p)", ExpressionAttributeValues={":p": "STATS#"}
            )
            items = response.get("Items", [])
            totals: Dict[str, float] = {}
            for item in items:
                name = item["PK"].replace("STATS#", "")
                amount = float(item["net_amount"])
                totals[name] = totals.get(name, 0.0) + amount

            sorted_totals = sorted(totals.items(), key=lambda x: x[1], reverse=True)
            return sorted_totals
        except ClientError:
            logger.exception("Failed to get leaderboard")
            return []

    def save_poll_metadata(
        self, week_id: str, channel_id: str, message_ts: str, emoji_mapping: Dict[str, str]
    ) -> bool:
        """
        Stores metadata for the weekly scheduling poll.

        PK: POLL#<week_id>, SK: METADATA
        """
        try:
            self.table.put_item(
                Item={
                    "PK": f"POLL#{week_id}",
                    "SK": "METADATA",
                    "channel_id": channel_id,
                    "message_ts": message_ts,
                    "emoji_mapping": emoji_mapping,
                }
            )
            return True
        except ClientError:
            logger.exception(f"Failed to save poll metadata for {week_id}")
            return False

    def get_poll_metadata(self, week_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves metadata for a specific weekly poll.
        """
        try:
            response = self.table.get_item(Key={"PK": f"POLL#{week_id}", "SK": "METADATA"})
            return response.get("Item")
        except ClientError:
            logger.exception(f"Failed to get poll metadata for {week_id}")
            return None

    def delete_game(self, game_id: str) -> bool:
        """
        Deletes a game record and all associated player stats entries.

        Removes: PK: GAME#<game_id> SK: RESULT
                 PK: STATS#<name>   SK: GAME#<game_id>  (for every player in the game)
        """
        try:
            game_pk = f"GAME#{game_id}"
            game_sk = "RESULT"

            # Fetch the game first to know which player stats to remove
            response = self.table.get_item(Key={"PK": game_pk, "SK": game_sk})
            item = response.get("Item")
            player_names = list(item["player_data"].keys()) if item else []

            # Delete the game record
            self.table.delete_item(Key={"PK": game_pk, "SK": game_sk})

            # Delete each player's stat entry for this game
            for name in player_names:
                self.table.delete_item(
                    Key={"PK": f"STATS#{name.lower().strip()}", "SK": f"GAME#{game_id}"}
                )

            logger.info(f"Deleted game {game_id} and {len(player_names)} stat entries.")
            return True
        except ClientError:
            logger.exception(f"Failed to delete game {game_id}")
            return False

    def rename_player_across_all_games(self, old_name: str, new_name: str) -> Dict[str, int]:
        """
        Renames a player across every GAME record and all STATS entries.

        For each GAME#* RESULT record that contains old_name in player_data:
          - Merges old_name's amount into new_name (additive if new_name already exists).
          - Removes old_name from the record.
          - Overwrites the GAME record.
          - Deletes STATS#<old_name> SK: GAME#<game_id>.
          - Writes/merges STATS#<new_name> SK: GAME#<game_id>.

        Returns:
            {"games_updated": N, "stats_updated": N}
        """
        old_key = old_name.lower().strip()
        new_key = new_name.lower().strip()
        games_updated = 0
        stats_updated = 0

        try:
            # Scan all GAME RESULT records
            response = self.table.scan(
                FilterExpression="SK = :s",
                ExpressionAttributeValues={":s": "RESULT"},
            )
            game_items = response.get("Items", [])

            for item in game_items:
                player_data: Dict[str, Any] = dict(item.get("player_data", {}))

                # Normalise keys for comparison but preserve original casing for lookup
                matches = [k for k in player_data if k.lower().strip() == old_key]
                if not matches:
                    continue

                game_id = item["PK"].replace("GAME#", "")
                now = item.get("timestamp", "")

                # Merge all matching old-name amounts into new_name
                for old_match in matches:
                    amount = float(player_data.pop(old_match))
                    existing = next(
                        (v for k, v in player_data.items() if k.lower().strip() == new_key),
                        None,
                    )
                    if existing is not None:
                        # new_name already in this game — add amounts
                        new_match = next(k for k in player_data if k.lower().strip() == new_key)
                        player_data[new_match] = float(player_data[new_match]) + amount
                    else:
                        player_data[new_name] = amount

                # Overwrite the GAME record with updated player_data
                self.table.put_item(
                    Item=to_decimal(
                        {
                            **item,
                            "player_data": player_data,
                        }
                    )
                )

                # Delete old STATS entry, write new one
                self.table.delete_item(Key={"PK": f"STATS#{old_key}", "SK": f"GAME#{game_id}"})
                new_amount = float(
                    next(v for k, v in player_data.items() if k.lower().strip() == new_key)
                )
                self.table.put_item(
                    Item=to_decimal(
                        {
                            "PK": f"STATS#{new_key}",
                            "SK": f"GAME#{game_id}",
                            "net_amount": new_amount,
                            "timestamp": now,
                        }
                    )
                )

                games_updated += 1
                stats_updated += 1

            logger.info(
                f"rename_player_across_all_games: '{old_name}' -> '{new_name}', "
                f"games_updated={games_updated}, stats_updated={stats_updated}"
            )
            return {"games_updated": games_updated, "stats_updated": stats_updated}

        except ClientError:
            logger.exception(f"Failed to rename player '{old_name}' -> '{new_name}'")
            return {"games_updated": 0, "stats_updated": 0}

    def get_poll(self, week_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the poll vote data.
        """
        try:
            response = self.table.get_item(Key={"PK": f"POLL#{week_id}", "SK": "VOTES"})
            return response.get("Item")
        except ClientError:
            logger.exception(f"Failed to get poll {week_id}")
            return None
