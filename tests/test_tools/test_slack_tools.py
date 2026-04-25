import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../poker_worker")))

from tools.slack_tools import (
    is_bot_in_thread,
    slack_react,
    slack_recent_channel_history,
)


class TestIsBotInThread(unittest.TestCase):
    """Regression tests for the previously-commented-out is_bot_in_thread fix."""

    def test_returns_true_when_bot_has_posted(self):
        mock_slack = MagicMock()
        mock_slack.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN", "text": "hey"},
                {"user": "U_BOT", "text": "sure"},
            ]
        }
        result = is_bot_in_thread("C1", "111.0", bot_user_id="U_BOT", slack_client=mock_slack)
        self.assertTrue(result)
        mock_slack.conversations_replies.assert_called_once_with(channel="C1", ts="111.0", limit=50)

    def test_returns_false_when_bot_has_not_posted(self):
        mock_slack = MagicMock()
        mock_slack.conversations_replies.return_value = {
            "messages": [
                {"user": "U_HUMAN_1", "text": "hey"},
                {"user": "U_HUMAN_2", "text": "yo"},
            ]
        }
        result = is_bot_in_thread("C1", "111.0", bot_user_id="U_BOT", slack_client=mock_slack)
        self.assertFalse(result)

    def test_returns_false_on_slack_api_error(self):
        from slack_sdk.errors import SlackApiError

        mock_slack = MagicMock()
        mock_slack.conversations_replies.side_effect = SlackApiError(
            "channel_not_found", {"error": "channel_not_found"}
        )
        result = is_bot_in_thread("C1", "111.0", bot_user_id="U_BOT", slack_client=mock_slack)
        self.assertFalse(result)

    def test_returns_false_on_empty_thread(self):
        mock_slack = MagicMock()
        mock_slack.conversations_replies.return_value = {"messages": []}
        result = is_bot_in_thread("C1", "111.0", bot_user_id="U_BOT", slack_client=mock_slack)
        self.assertFalse(result)


class TestSlackRecentChannelHistory(unittest.TestCase):
    def test_channel_history_reversed(self):
        mock_slack = MagicMock()
        mock_slack.conversations_history.return_value = {
            "messages": [{"user": "U1", "text": "second"}, {"user": "U2", "text": "first"}]
        }
        result = slack_recent_channel_history("C1", slack_client=mock_slack)
        self.assertEqual(result["status"], "success")
        # Reversed means first message appears first in output
        self.assertIn("<@U2>: first\n<@U1>: second", result["data"])

    def test_thread_history_not_reversed(self):
        mock_slack = MagicMock()
        mock_slack.conversations_replies.return_value = {
            "messages": [{"user": "U1", "text": "parent"}, {"user": "U2", "text": "reply"}]
        }
        result = slack_recent_channel_history("C1", slack_client=mock_slack, thread_ts="111.0")
        self.assertEqual(result["status"], "success")
        self.assertIn("<@U1>: parent\n<@U2>: reply", result["data"])

    def test_slack_api_error(self):
        from slack_sdk.errors import SlackApiError

        mock_slack = MagicMock()
        mock_slack.conversations_history.side_effect = SlackApiError(
            "not_in_channel", {"error": "not_in_channel"}
        )
        result = slack_recent_channel_history("C1", slack_client=mock_slack)
        self.assertEqual(result["status"], "failure")
        self.assertIn("not_in_channel", result["error_message"])


class TestSlackReact(unittest.TestCase):
    def test_add_reaction(self):
        mock_slack = MagicMock()
        result = slack_react("C1", "111.0", "thumbsup", slack_client=mock_slack)
        self.assertEqual(result["status"], "success")
        mock_slack.reactions_add.assert_called_once_with(
            channel="C1", timestamp="111.0", name="thumbsup"
        )

    def test_remove_reaction(self):
        mock_slack = MagicMock()
        result = slack_react("C1", "111.0", "thumbsup", slack_client=mock_slack, action="remove")
        self.assertEqual(result["status"], "success")
        mock_slack.reactions_remove.assert_called_once_with(
            channel="C1", timestamp="111.0", name="thumbsup"
        )

    def test_slack_api_error(self):
        from slack_sdk.errors import SlackApiError

        mock_slack = MagicMock()
        mock_slack.reactions_add.side_effect = SlackApiError(
            "already_reacted", {"error": "already_reacted"}
        )
        result = slack_react("C1", "111.0", "thumbsup", slack_client=mock_slack)
        self.assertEqual(result["status"], "failure")
        self.assertIn("already_reacted", result["error_message"])


if __name__ == "__main__":
    unittest.main()
