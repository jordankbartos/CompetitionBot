import datetime
import hashlib
import json
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../poker_worker")))

from tools.settlement_tools import (
    calculate_poker_settlements,
    delete_game_result,
    find_recent_game,
    overwrite_game_result,
    record_game_result,
    rename_player_in_game_history,
)

JORDAN_ID = "U_JORDAN"
OTHER_ID = "U_OTHER"


class TestCalculatePokerSettlements(unittest.TestCase):
    def _make_db(self, users):
        mock_db = MagicMock()
        mock_db.get_all_users.return_value = users
        return mock_db

    def test_with_splits(self):
        mock_db = self._make_db(
            [
                {"poker_name": "Alice", "venmo_handle": "@alice_v", "PK": "USER#U1"},
                {"poker_name": "Bob", "venmo_handle": "@bob_v", "PK": "USER#U2"},
            ]
        )
        result = calculate_poker_settlements(
            [{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}], db=mock_db
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("*Settlement Plan:*", result["data"])
        self.assertIn("pays *Alice*", result["data"])
        self.assertIn("Pay @alice_v", result["data"])

    def test_no_splits_when_even(self):
        mock_db = self._make_db([])
        result = calculate_poker_settlements(
            [{"name": "Alice", "amount": 0.0}, {"name": "Bob", "amount": 0.0}], db=mock_db
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], "Everyone is even! No settlements needed.")

    def test_strips_parenthetical_from_names(self):
        mock_db = self._make_db(
            [
                {"poker_name": "Alice", "venmo_handle": "@alice_v", "PK": "USER#U1"},
                {"poker_name": "Bob", "venmo_handle": "@bob_v", "PK": "USER#U2"},
            ]
        )
        result = calculate_poker_settlements(
            [{"name": "Alice (left)", "amount": 10.0}, {"name": "Bob (host)", "amount": -10.0}],
            db=mock_db,
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("pays *Alice*", result["data"])

    def test_unregistered_creditor_shows_registration_prompt(self):
        mock_db = self._make_db([])  # No users registered
        result = calculate_poker_settlements(
            [{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}], db=mock_db
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("Please register Alice", result["data"])


class TestRecordGameResult(unittest.TestCase):
    def test_success_on_new_game(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = []
        mock_db.save_game.return_value = True
        result = record_game_result(
            [{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}],
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "success")
        mock_db.save_game.assert_called_once()

    def test_rejects_exact_duplicate(self):
        player_data = {"Alice": 10.0, "Bob": -10.0}
        fingerprint = hashlib.md5(json.dumps(sorted(player_data.items())).encode()).hexdigest()
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = [
            {"fingerprint": fingerprint, "uploader_id": "U_SOMEONE"}
        ]
        result = record_game_result(
            [{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}],
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("already recorded", result["error_message"])

    def test_requests_jordan_confirmation_for_similar_recent_game(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = [
            {
                "fingerprint": "different",
                "player_data": {"Alice": 5.0, "Bob": -5.0},
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        ]
        result = record_game_result(
            [{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}],
            uploader_id=OTHER_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("overwrite", result["error_message"].lower())

    def test_rejects_force_overwrite_by_non_jordan(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = [
            {
                "fingerprint": "different",
                "player_data": {"Alice": 5.0, "Bob": -5.0},
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        ]
        result = record_game_result(
            [{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}],
            uploader_id=OTHER_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
            force_overwrite=True,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("Jordan", result["error_message"])

    def test_allows_force_overwrite_by_jordan(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = [
            {
                "fingerprint": "different",
                "player_data": {"Alice": 5.0, "Bob": -5.0},
                "timestamp": datetime.datetime.utcnow().isoformat(),
            }
        ]
        mock_db.save_game.return_value = True
        result = record_game_result(
            [{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}],
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
            force_overwrite=True,
        )
        self.assertEqual(result["status"], "success")


class TestFindRecentGame(unittest.TestCase):
    def _make_games(self):
        return [
            {
                "PK": "GAME#AUTO-20260101-120000",
                "timestamp": "2026-01-01T12:00:00",
                "uploader_id": JORDAN_ID,
                "player_data": {"Alice": 10.0, "Bob": -10.0},
            },
            {
                "PK": "GAME#AUTO-20260108-180000",
                "timestamp": "2026-01-08T18:00:00",
                "uploader_id": JORDAN_ID,
                "player_data": {"Charlie": 20.0, "Dave": -20.0},
            },
        ]

    def test_returns_all_when_no_search_term(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = self._make_games()
        result = find_recent_game(search_term=None, db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["data"]), 2)

    def test_filters_by_player_name(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = self._make_games()
        result = find_recent_game(search_term="Alice", db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["data"]), 1)
        self.assertIn("Alice", result["data"][0]["players"])

    def test_filters_by_game_id_substring(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = self._make_games()
        result = find_recent_game(search_term="20260108", db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["data"]), 1)

    def test_returns_empty_list_when_no_games(self):
        mock_db = MagicMock()
        mock_db.get_recent_games.return_value = []
        result = find_recent_game(search_term="anything", db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], [])


class TestOverwriteGameResult(unittest.TestCase):
    def test_rejects_non_jordan_uploader(self):
        mock_db = MagicMock()
        result = overwrite_game_result(
            game_id="G1",
            player_results=[{"name": "Alice", "amount": 10.0}],
            uploader_id=OTHER_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("Jordan", result["error_message"])
        mock_db.save_game.assert_not_called()

    def test_allows_jordan_uploader(self):
        mock_db = MagicMock()
        mock_db.save_game.return_value = True
        result = overwrite_game_result(
            game_id="G1",
            player_results=[{"name": "Alice", "amount": 10.0}, {"name": "Bob", "amount": -10.0}],
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "success")
        mock_db.save_game.assert_called_once()

    def test_db_failure_returns_failure(self):
        mock_db = MagicMock()
        mock_db.save_game.return_value = False
        result = overwrite_game_result(
            game_id="G1",
            player_results=[{"name": "Alice", "amount": 10.0}],
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")


class TestDeleteGameResult(unittest.TestCase):
    def test_rejects_non_jordan_uploader(self):
        mock_db = MagicMock()
        result = delete_game_result(
            game_id="G1",
            uploader_id=OTHER_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("Jordan", result["error_message"])
        mock_db.delete_game.assert_not_called()

    def test_allows_jordan_uploader(self):
        mock_db = MagicMock()
        mock_db.delete_game.return_value = True
        result = delete_game_result(
            game_id="G1",
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "success")
        mock_db.delete_game.assert_called_once_with("G1")

    def test_db_failure_returns_failure(self):
        mock_db = MagicMock()
        mock_db.delete_game.return_value = False
        result = delete_game_result(
            game_id="G1",
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")


class TestRenamePlayerInGameHistory(unittest.TestCase):
    def test_rejects_non_jordan_uploader(self):
        mock_db = MagicMock()
        result = rename_player_in_game_history(
            old_name="Reece (left)",
            new_name="Reece",
            uploader_id=OTHER_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("Jordan", result["error_message"])
        mock_db.rename_player_across_all_games.assert_not_called()

    def test_rejects_empty_old_name(self):
        mock_db = MagicMock()
        result = rename_player_in_game_history(
            old_name="   ",
            new_name="Reece",
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("non-empty", result["error_message"])
        mock_db.rename_player_across_all_games.assert_not_called()

    def test_rejects_empty_new_name(self):
        mock_db = MagicMock()
        result = rename_player_in_game_history(
            old_name="Reece (left)",
            new_name="",
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("non-empty", result["error_message"])

    def test_success_reports_games_and_stats_updated(self):
        mock_db = MagicMock()
        mock_db.rename_player_across_all_games.return_value = {
            "games_updated": 3,
            "stats_updated": 3,
        }
        result = rename_player_in_game_history(
            old_name="Reece (left)",
            new_name="Reece",
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("3 game record(s)", result["data"])
        mock_db.rename_player_across_all_games.assert_called_once_with(
            old_name="Reece (left)", new_name="Reece"
        )

    def test_success_no_matching_games(self):
        mock_db = MagicMock()
        mock_db.rename_player_across_all_games.return_value = {
            "games_updated": 0,
            "stats_updated": 0,
        }
        result = rename_player_in_game_history(
            old_name="Ghost",
            new_name="Reece",
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("No game records found", result["data"])

    def test_db_exception_returns_failure(self):
        mock_db = MagicMock()
        mock_db.rename_player_across_all_games.side_effect = Exception("DynamoDB timeout")
        result = rename_player_in_game_history(
            old_name="Reece (left)",
            new_name="Reece",
            uploader_id=JORDAN_ID,
            jordan_id=JORDAN_ID,
            db=mock_db,
        )
        self.assertEqual(result["status"], "failure")
        self.assertIn("DynamoDB timeout", result["error_message"])


if __name__ == "__main__":
    unittest.main()
