"""
AINewsAgent: queryable AI news and developments assistant.

Uses a plain function tool that calls google.genai.Client with search grounding
internally. This avoids the Gemini API constraint that prevents combining built-in
tools (google_search) with function declarations in the same ADK request — the
grounding happens in an isolated genai call, completely outside ADK's tool pipeline.
"""

from config import AI_NEWS_AGENT_INSTRUCTION, MODEL_HEAVY, MODEL_LIGHT
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.genai import Client
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool
from logging_utils import get_logger

logger = get_logger(__name__)


def build_ai_news_agent(google_api_key: str) -> Agent:
    """Constructs and returns the AINewsAgent LlmAgent."""
    model = Gemini(model=MODEL_LIGHT, api_key=google_api_key)

    def _search_web(query: str) -> str:
        """Search the web for current information about the given query.

        Returns a summarized answer with source URLs drawn from live search results.
        Always prefer queries that include a recency signal like "past week" or a year.
        """
        client = Client(api_key=google_api_key)
        response = client.models.generate_content(
            model=MODEL_HEAVY,
            contents=(
                f"{query}\n\n"
                "Include URLs for every specific source, tool, or article you mention."
            ),
            config=GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())]),
        )
        return response.text or ""

    logger.info("Building AINewsAgent")
    return Agent(
        name="AINewsAgent",
        model=model,
        instruction=AI_NEWS_AGENT_INSTRUCTION,
        tools=[_search_web],
    )
