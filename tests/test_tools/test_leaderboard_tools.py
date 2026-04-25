import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../poker_worker")))

from tools.leaderboard import get_poker_leaderboard


class TestGetPokerLeaderboard(unittest.TestCase):
    def test_with_data(self):
        mock_db = MagicMock()
        mock_db.get_leaderboard.return_value = [("alice", 100.0), ("bob", -50.0)]
        result = get_poker_leaderboard(db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertIn("All-Time Leaderboard", result["data"])
        self.assertIn("Alice", result["data"])
        self.assertIn("100.00", result["data"])
        self.assertIn("Bob", result["data"])
        self.assertIn("-50.00", result["data"])

    def test_no_data(self):
        mock_db = MagicMock()
        mock_db.get_leaderboard.return_value = []
        result = get_poker_leaderboard(db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], "No game data found yet!")

    def test_medals_assigned(self):
        mock_db = MagicMock()
        mock_db.get_leaderboard.return_value = [
            ("alice", 100.0),
            ("bob", 50.0),
            ("charlie", -20.0),
            ("dave", -130.0),
        ]
        result = get_poker_leaderboard(db=mock_db)
        self.assertIn("🥇", result["data"])
        self.assertIn("🥈", result["data"])
        self.assertIn("🥉", result["data"])
        self.assertIn("- Dave", result["data"])

    def test_db_exception(self):
        mock_db = MagicMock()
        mock_db.get_leaderboard.side_effect = Exception("timeout")
        result = get_poker_leaderboard(db=mock_db)
        self.assertEqual(result["status"], "failure")
        self.assertIn("timeout", result["error_message"])


if __name__ == "__main__":
    unittest.main()
