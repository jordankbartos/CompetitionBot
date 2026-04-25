import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../poker_worker")))

from tools.poll import get_weekly_poll_results


class TestGetWeeklyPollResults(unittest.TestCase):
    def test_returns_tally_with_bot_vote_subtracted(self):
        mock_db = MagicMock()
        mock_db.get_poll_metadata.return_value = {
            "channel_id": "C123",
            "message_ts": "123.456",
            "emoji_mapping": {"monday": "Mon", "tuesday": "Tue"},
        }
        mock_slack = MagicMock()
        mock_slack.reactions_get.return_value = {
            "message": {
                "reactions": [
                    {"name": "monday", "count": 2},  # 1 real vote
                    {"name": "tuesday", "count": 3},  # 2 real votes
                ]
            }
        }
        result = get_weekly_poll_results(db=mock_db, slack_client=mock_slack)
        self.assertEqual(result["status"], "success")
        self.assertIn("Tue: 2", result["data"])
        self.assertIn("Mon: 1", result["data"])

    def test_no_poll_this_week(self):
        mock_db = MagicMock()
        mock_db.get_poll_metadata.return_value = None
        result = get_weekly_poll_results(db=mock_db, slack_client=MagicMock())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"], "No poll found for this week.")

    def test_db_exception(self):
        mock_db = MagicMock()
        mock_db.get_poll_metadata.side_effect = Exception("DB error")
        result = get_weekly_poll_results(db=mock_db, slack_client=MagicMock())
        self.assertEqual(result["status"], "failure")
        self.assertIn("DB error", result["error_message"])


if __name__ == "__main__":
    unittest.main()
