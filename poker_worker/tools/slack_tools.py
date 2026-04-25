"""
Tools for Slack interactions: history, reactions, search, file downloads,
and thread-presence checks.
"""

from typing import Any, Dict, Literal, Optional

import requests
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from logging_utils import get_logger
from slack_sdk.errors import SlackApiError

logger = get_logger(__name__)


def is_bot_in_thread(channel_id: str, thread_ts: str, bot_user_id: str, slack_client: Any) -> bool:
    """Returns True if the bot has already posted in the given thread.

    Used to decide whether to respond to a non-mention thread reply.

    Args:
        channel_id: The Slack channel ID.
        thread_ts: The parent message timestamp of the thread.
        bot_user_id: The bot's Slack user ID.
        slack_client: Slack WebClient instance.
    """
    logger.info(f"is_bot_in_thread invoked: channel={channel_id}, thread_ts={thread_ts}")
    try:
        response = slack_client.conversations_replies(channel=channel_id, ts=thread_ts, limit=50)
        messages = response.get("messages", [])
        in_thread = any(msg.get("user") == bot_user_id for msg in messages)
        logger.info(f"is_bot_in_thread result: {in_thread}")
        return in_thread
    except SlackApiError:
        logger.exception(f"is_bot_in_thread failed for channel={channel_id}, thread_ts={thread_ts}")
        return False


def slack_recent_channel_history(
    channel_id: str, slack_client: Any, limit: int = 20, thread_ts: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieves the most recent messages in a channel or thread.

    Args:
        channel_id: The Slack channel ID.
        slack_client: Slack WebClient instance.
        limit: Number of messages to retrieve (default 20).
        thread_ts: Parent message timestamp if fetching a thread.

    Returns:
        Dict with "status", "data" (formatted messages string), "error_message".
    """
    logger.info(
        f"Tool slack_recent_channel_history invoked: channel={channel_id}, limit={limit}, thread_ts={thread_ts}"
    )
    try:
        if thread_ts:
            response = slack_client.conversations_replies(
                channel=channel_id, ts=thread_ts, limit=limit
            )
        else:
            response = slack_client.conversations_history(channel=channel_id, limit=limit)

        messages = response.get("messages", [])
        if not thread_ts or thread_ts == "None":
            messages = list(reversed(messages))

        formatted = [f"<@{msg.get('user', 'Bot')}>: {msg.get('text', '')}" for msg in messages]
        logger.info(
            f"Tool slack_recent_channel_history: retrieved {len(messages)} messages from {channel_id}."
        )
        return {"status": "success", "data": "\n".join(formatted), "error_message": None}
    except SlackApiError as e:
        logger.exception(f"Tool slack_recent_channel_history failed for channel={channel_id}")
        return {
            "status": "failure",
            "data": None,
            "error_message": f"Failed to retrieve history: {e.response.get('error', str(e))}",
        }
    except Exception as e:
        logger.exception("Error in slack_recent_channel_history")
        return {"status": "failure", "data": None, "error_message": str(e)}


def slack_react(
    channel_id: str, timestamp: str, emoji: str, slack_client: Any, action: str = "add"
) -> Dict[str, Any]:
    """Adds or removes an emoji reaction from a message.

    Args:
        channel_id: The Slack channel ID.
        timestamp: The message timestamp.
        emoji: Emoji name without colons (e.g., 'thumbsup').
        slack_client: Slack WebClient instance.
        action: 'add' or 'remove' (default 'add').

    Returns:
        Dict with "status", "data", "error_message".
    """
    logger.info(
        f"Tool slack_react: channel={channel_id}, ts={timestamp}, emoji={emoji}, action={action}"
    )
    try:
        if action == "add":
            slack_client.reactions_add(channel=channel_id, timestamp=timestamp, name=emoji)
        else:
            slack_client.reactions_remove(channel=channel_id, timestamp=timestamp, name=emoji)
        logger.info(f"Tool slack_react: {action} '{emoji}' on {timestamp} succeeded.")
        return {"status": "success", "data": "Reaction updated.", "error_message": None}
    except SlackApiError as e:
        logger.exception(f"Tool slack_react failed: channel={channel_id}, emoji={emoji}")
        return {
            "status": "failure",
            "data": None,
            "error_message": f"Failed to update reaction: {e.response.get('error', str(e))}",
        }
    except Exception as e:
        logger.exception("Error in slack_react")
        return {"status": "failure", "data": None, "error_message": str(e)}


def get_message_files(channel_id: str, message_ts: str, slack_client: Any) -> Dict[str, Any]:
    """Fetches file attachment metadata for a specific Slack message.

    Use this after slack_search identifies a message with a file: pass the channel_id
    and message_ts from the search result to retrieve the file IDs needed for
    save_slack_file_as_artifact.

    Args:
        channel_id: The Slack channel ID containing the message.
        message_ts: The message timestamp (ts) from a slack_search result.
        slack_client: Slack WebClient instance.

    Returns:
        Dict with "status", "files" (list of {id, name, mimetype}), "error_message".
    """
    logger.info(f"Tool get_message_files invoked: channel={channel_id}, ts={message_ts}")
    try:
        response = slack_client.conversations_history(
            channel=channel_id,
            oldest=message_ts,
            latest=message_ts,
            inclusive=True,
            limit=1,
        )
        messages = response.get("messages", [])
        msg = next((m for m in messages if m.get("ts") == message_ts), None)
        if msg is None:
            return {"status": "failure", "files": [], "error_message": "Message not found"}
        files = [
            {"id": f.get("id"), "name": f.get("name"), "mimetype": f.get("mimetype")}
            for f in msg.get("files", [])
        ]
        logger.info(f"Tool get_message_files: found {len(files)} file(s) on message {message_ts}")
        return {"status": "success", "files": files, "error_message": None}
    except SlackApiError as e:
        logger.exception(f"Tool get_message_files failed: channel={channel_id}, ts={message_ts}")
        return {
            "status": "failure",
            "files": [],
            "error_message": f"Slack error: {e.response.get('error', str(e))}",
        }
    except Exception as e:
        logger.exception("Error in get_message_files")
        return {"status": "failure", "files": [], "error_message": str(e)}


async def save_slack_file_as_artifact(
    file_id: str, tool_context: ToolContext, slack_client: Any, slack_token: str
) -> Dict[str, Any]:
    """Downloads a Slack file and saves it as an ADK artifact for later inspection.

    Does NOT return the file contents directly. After calling this, you MUST call
    LoadArtifacts with the returned filename to load the file into context before
    you can describe or use its contents.

    Args:
        file_id: The Slack file ID (e.g., 'F12345678').
        tool_context: ADK ToolContext for artifact storage.
        slack_client: Slack WebClient instance.
        slack_token: Bot OAuth token for authenticated download.

    Returns:
        Dict with "status", "mime_type", "filename", "version", "message".
        Use "filename" as the artifact name to pass to LoadArtifacts.
    """
    logger.info(f"Tool save_slack_file_as_artifact invoked for file_id: {file_id}")
    try:
        result = slack_client.files_info(file=file_id)
        file_url = result["file"]["url_private"]
        mime_type = result["file"].get("mimetype", "application/octet-stream")

        headers = {"Authorization": f"Bearer {slack_token}"}
        response = requests.get(file_url, headers=headers, timeout=15)
        response.raise_for_status()
        raw_data = response.content

        if len(raw_data) > 3_000_000:
            raise ValueError("File too large, rejected")

        m_type, _, m_ext = mime_type.partition("/")

        match m_type:
            case "image":
                artifact_name = f"slack_image_{file_id}.{m_ext}"
                data = types.Part.from_bytes(data=raw_data, mime_type=mime_type)
            case "text" | "application" if m_ext in ("json", "javascript", "xml", "plain"):
                artifact_name = f"text_file_{file_id}.{m_ext}"
                data = types.Part.from_text(text=raw_data.decode("utf-8", errors="replace"))
            case "video" | "audio" | "application":
                artifact_name = f"media_file_{file_id}.{m_ext}"
                data = types.Part.from_bytes(data=raw_data, mime_type=mime_type)
            case _:
                raise ValueError(f"Invalid or unsupported mimetype: {mime_type}")

        version = await tool_context.save_artifact(filename=artifact_name, artifact=data)
        logger.info(f"Tool save_slack_file_as_artifact: saved {artifact_name} (version {version})")
        return {
            "status": "success",
            "mime_type": mime_type,
            "filename": artifact_name,
            "version": version,
            "message": f"File of type {mime_type} saved to context",
        }
    except SlackApiError as e:
        logger.exception(f"Tool save_slack_file_as_artifact: Slack API error for file {file_id}")
        return {
            "status": "failure",
            "data": None,
            "error_message": f"Slack error: {e.response.get('error', str(e))}",
        }
    except Exception as e:
        logger.exception(f"Error in get_file_contents for file {file_id}")
        return {"status": "failure", "data": None, "error_message": str(e)}


def create_slack_search_tool(action_token: str, slack_client: Any):
    """Factory that returns a slack_search function bound to an action_token.

    Args:
        action_token: The Slack assistant action token for search.
        slack_client: Slack WebClient instance.
    """

    def slack_search(
        query: str,
        modifiers: Optional[str] = None,
        include_bots: bool = True,
        include_context_messages: bool = False,
        limit: int = 20,
        sort: Literal["score", "timestamp"] = "score",
        sort_dir: Literal["asc", "desc"] = "desc",
        include_message_blocks: bool = True,
        before: Optional[int] = None,
        after: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search across the Slack workspace for messages, files, channels, and users.

        IMPORTANT — two separate fields serve different purposes:
          • query: Keywords only — plain search terms, no sentences or Slack operators.
                   Example: "poker game results" or "png file"
          • modifiers: All Slack filter operators as a space-separated string.
                   Channel, user, date, and content-type filters ALL go here.
                   Example: "from:<@U123456> in:<#C123456> has:file"

        Supported modifiers:
          - from:<@UID>         filter by message author (use Slack user ID)
          - in:<#CID>           filter to a specific channel (use Slack channel ID)
          - has:file            only messages with file attachments
          - has:pin             only pinned messages
          - has:reaction        only messages with reactions
          - is:thread           only thread messages
          - before:YYYY-MM-DD   results before a date
          - after:YYYY-MM-DD    results after a date
          - type:pdf / type:png file type filter

        For simply gathering recent conversation history, prefer slack_recent_channel_history.

        Args:
            query: Keywords only. No Slack operators — those go in modifiers.
            modifiers: Space-separated Slack filter operators (from:, in:, has:, etc.).
            include_bots: Whether to include bot messages (default True).
            include_context_messages: Whether to include surrounding context messages (default False).
            sort: 'score' for relevance, 'timestamp' for chronological (default 'score').
            sort_dir: 'asc' or 'desc' (default 'desc').
            include_message_blocks: Whether to return full message block content (default True).
            limit: Number of results to return, max 20 (default 20).
            before: UNIX timestamp — only return results before this time.
            after: UNIX timestamp — only return results after this time.
            cursor: Pagination cursor from a previous response.

        Returns:
            Dict with "status", "results", "response_metadata", "error_message".
        """
        payload = {
            "query": query,
            "action_token": action_token,
            "limit": limit,
            "sort": sort,
            "sort_dir": sort_dir,
            "include_bots": include_bots,
            "include_context_messages": include_context_messages,
            "include_message_blocks": include_message_blocks,
            "channel_types": ["public_channel", "private_channel"],
            "content_types": ["messages", "files"],
        }
        optional_args = {"before": before, "after": after, "modifiers": modifiers, "cursor": cursor}
        payload.update({k: v for k, v in optional_args.items() if v is not None})

        logger.info(f"Tool slack_search invoked with query: {payload}")
        try:
            response = slack_client.api_call("assistant.search.context", json=payload)
        except SlackApiError as e:
            logger.exception("Tool slack_search: Slack API error")
            return {
                "status": "failure",
                "results": None,
                "response_metadata": None,
                "error_message": f"Search failed: {e.response.get('error', str(e))}",
            }

        try:
            logger.info(f"{response=}")
            logger.info(f"{response.__dict__=}")
            if response["ok"]:
                results = response.get("results", {})
                logger.info(f"Got results: {results}")
                return {
                    "status": "success",
                    "results": results,
                    "response_metadata": response.get("response_metadata"),
                    "error_message": None,
                }
            else:
                return {
                    "status": "failure",
                    "results": None,
                    "response_metadata": None,
                    "error_message": response.get("error"),
                }
        except Exception as e:
            logger.exception(f"Tool slack_search: unexpected error parsing response: {response}")
            return {
                "status": "failure",
                "results": None,
                "response_metadata": None,
                "error_message": f"Unexpected error: {e}",
            }

    return slack_search
