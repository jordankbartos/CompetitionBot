import os
import sys
import unittest
from unittest.mock import MagicMock

# Stub missing non-project dependencies before any project imports
sys.modules.setdefault("pythonjsonlogger", MagicMock())
sys.modules.setdefault("pythonjsonlogger.jsonlogger", MagicMock())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../poker_worker")))


def _build_coordinator(action_token=None):
    from agents.workspace_coordinator import build_workspace_coordinator

    return build_workspace_coordinator(
        db=MagicMock(),
        slack_client=MagicMock(),
        slack_token="xoxb-test",
        google_api_key="fake-key",
        jordan_id="U_JORDAN",
        bot_user_id="U_BOT",
        action_token=action_token,
    )


class TestWorkspaceCoordinatorStructure(unittest.TestCase):
    def test_returns_agent_named_workspace_coordinator(self):
        agent = _build_coordinator()
        self.assertEqual(agent.name, "WorkspaceCoordinator")

    def test_has_exactly_three_sub_agents(self):
        agent = _build_coordinator()
        self.assertEqual(len(agent.sub_agents), 3)

    def test_first_sub_agent_is_poker_coordinator(self):
        agent = _build_coordinator()
        self.assertEqual(agent.sub_agents[0].name, "PokerCoordinator")

    def test_second_sub_agent_is_robo_duder(self):
        agent = _build_coordinator()
        self.assertEqual(agent.sub_agents[1].name, "RoboDuder")

    def test_third_sub_agent_is_ai_news_agent(self):
        agent = _build_coordinator()
        self.assertEqual(agent.sub_agents[2].name, "AINewsAgent")

    def test_ai_news_agent_has_search_web_tool(self):
        agent = _build_coordinator()
        ai_news = agent.sub_agents[2]
        tool_names = {getattr(t, "__name__", type(t).__name__) for t in ai_news.tools}
        self.assertIn("_search_web", tool_names)

    def test_ai_news_agent_has_no_slack_or_db_tools(self):
        agent = _build_coordinator()
        ai_news = agent.sub_agents[2]
        tool_names = {getattr(t, "__name__", type(t).__name__) for t in ai_news.tools}
        self.assertNotIn("_slack_recent_channel_history", tool_names)
        self.assertNotIn("_get_poker_leaderboard", tool_names)

    def test_poker_coordinator_has_three_sub_agents(self):
        agent = _build_coordinator()
        sub_names = {a.name for a in agent.sub_agents[0].sub_agents}
        self.assertEqual(sub_names, {"SettlementAgent", "LeaderboardAgent", "ChatAgent"})

    def test_robo_duder_has_no_poker_domain_tools(self):
        agent = _build_coordinator()
        robo = agent.sub_agents[1]
        tool_names = {getattr(t, "__name__", type(t).__name__) for t in robo.tools}
        self.assertNotIn("_register_player_venmo", tool_names)
        self.assertNotIn("_get_weekly_poll_results", tool_names)
        self.assertNotIn("_get_poker_leaderboard", tool_names)

    def test_robo_duder_without_action_token_has_no_search(self):
        agent = _build_coordinator(action_token=None)
        robo = agent.sub_agents[1]
        tool_names = {getattr(t, "__name__", "") for t in robo.tools}
        self.assertNotIn("slack_search", tool_names)

    def test_robo_duder_with_action_token_has_search(self):
        agent = _build_coordinator(action_token="xoxe-test")
        robo = agent.sub_agents[1]
        tool_names = {getattr(t, "__name__", "") for t in robo.tools}
        self.assertIn("slack_search", tool_names)


class TestWorkspaceCoordinatorInstruction(unittest.TestCase):
    def test_instruction_contains_pokerrrr_channel_id(self):
        from config import POKERRRR_CHANNEL_ID, WORKSPACE_COORDINATOR_INSTRUCTION

        self.assertIn(POKERRRR_CHANNEL_ID, WORKSPACE_COORDINATOR_INSTRUCTION)

    def test_instruction_routes_to_poker_coordinator(self):
        from config import WORKSPACE_COORDINATOR_INSTRUCTION

        self.assertIn("PokerCoordinator", WORKSPACE_COORDINATOR_INSTRUCTION)

    def test_instruction_routes_to_robo_duder(self):
        from config import WORKSPACE_COORDINATOR_INSTRUCTION

        self.assertIn("RoboDuder", WORKSPACE_COORDINATOR_INSTRUCTION)

    def test_instruction_routes_to_ai_news_agent(self):
        from config import WORKSPACE_COORDINATOR_INSTRUCTION

        self.assertIn("AINewsAgent", WORKSPACE_COORDINATOR_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
