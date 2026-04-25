import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../poker_worker")))

from tools.profile import get_user_profile, register_player_venmo


class TestGetUserProfile(unittest.TestCase):
    def test_found(self):
        mock_db = MagicMock()
        mock_db.get_user_by_slack_id.return_value = {
            "poker_name": "Alice",
            "venmo_handle": "@alice_v",
        }
        result = get_user_profile("U1", db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["poker_name"], "Alice")
        mock_db.get_user_by_slack_id.assert_called_once_with("U1")

    def test_not_found(self):
        mock_db = MagicMock()
        mock_db.get_user_by_slack_id.return_value = None
        result = get_user_profile("U1", db=mock_db)
        self.assertEqual(result["status"], "success")
        self.assertIsNone(result["data"])
        self.assertEqual(result["error_message"], "User profile not found.")

    def test_db_exception(self):
        mock_db = MagicMock()
        mock_db.get_user_by_slack_id.side_effect = Exception("DB error")
        result = get_user_profile("U1", db=mock_db)
        self.assertEqual(result["status"], "failure")
        self.assertIsNone(result["data"])
        self.assertIn("DB error", result["error_message"])


class TestRegisterPlayerVenmo(unittest.TestCase):
    def test_success_prepends_at(self):
        mock_db = MagicMock()
        mock_db.register_user.return_value = True
        result = register_player_venmo("U1", "Alice", "alice_v", db=mock_db)
        self.assertEqual(result["status"], "success")
        mock_db.register_user.assert_called_once_with("U1", "Alice", "@alice_v")

    def test_success_with_at_already(self):
        mock_db = MagicMock()
        mock_db.register_user.return_value = True
        result = register_player_venmo("U1", "Alice", "@alice_v", db=mock_db)
        self.assertEqual(result["status"], "success")
        mock_db.register_user.assert_called_once_with("U1", "Alice", "@alice_v")

    def test_db_returns_false(self):
        mock_db = MagicMock()
        mock_db.register_user.return_value = False
        result = register_player_venmo("U1", "Alice", "alice_v", db=mock_db)
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["data"], "Registration failed.")

    def test_db_exception(self):
        mock_db = MagicMock()
        mock_db.register_user.side_effect = Exception("conn error")
        result = register_player_venmo("U1", "Alice", "alice_v", db=mock_db)
        self.assertEqual(result["status"], "failure")
        self.assertIn("conn error", result["error_message"])


if __name__ == "__main__":
    unittest.main()
