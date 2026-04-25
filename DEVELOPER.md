# 🛠 Developer Guide

This document provides a deep dive into the architecture, design decisions, and internal logic of PokerBot.

---

## 📐 Architecture

PokerBot is built on a serverless architecture using AWS. It follows an asynchronous processing pattern to stay within Slack's 3-second response limit.

### High-Level Diagram

```mermaid
graph TD
    Slack[Slack API] -->|Webhook POST| APIGateway[AWS API Gateway]
    APIGateway -->|Trigger| Handler[poker_handler Lambda]
    Handler -->|1. Verify Sig| Handler
    Handler -->|2. Fast Ack| Slack
    Handler -->|3. Async Invoke| Worker[poker_worker Lambda]

    Worker -->|Read/Write| DynamoDB[(Amazon DynamoDB)]
    Worker -->|LLM Calls| Gemini[Google Gemini AI]
    Worker -->|Post Message| Slack

    EventBridge[AWS EventBridge] -->|Scheduled Trigger| Worker
```

### Components

1. **poker_handler (Lambda):** Signature verification, Slack challenge handling, async worker invocation.
2. **poker_worker (Lambda):** The "brain" of the bot — runs the PokerCoordinator agent graph.
3. **DynamoDB:** Single-table design (PK/SK). See schema below.
4. **Google Gemini:** Powers all agents via Google ADK.

---

## 🧠 Agent Architecture

The bot uses **Google ADK** with a coordinator + sub-agents pattern.

```
PokerCoordinator (LlmAgent, root)
│   Routes each incoming message to the correct specialist sub-agent.
│
├── SettlementAgent (LlmAgent)
│   │   Handles fresh screenshots AND game corrections.
│   │
│   └── SettlementPipeline (SequentialAgent, used as AgentTool)
│       ├── VisionStep        — parse screenshot → raw player amounts
│       ├── NameResolverStep  — fuzzy-match names to registered players
│       ├── CalculateStep     — deterministic debt calculation
│       ├── PersistStep       — save to DB; handles dup/Jordan-auth logic
│       └── FormatStep        — produce final Slack-formatted message
│
├── LeaderboardAgent (LlmAgent)
│       Read-only: get_poker_leaderboard, get_user_profile
│
└── ChatAgent (LlmAgent)
        Catch-all: registration, poll results, general conversation,
        file downloads, Slack search (when action_token is present)
```

**Routing logic:**
- Image attached OR settlement/payment/correction language → `SettlementAgent`
- Leaderboard / stats / ranking questions → `LeaderboardAgent`
- Everything else → `ChatAgent`

**EventBridge poll posting** runs entirely outside the agent graph — pure deterministic logic in `event_bridge_trigger.py`. No LLM involved.

### Future compatibility
`build_poker_coordinator(deps)` returns a standalone `LlmAgent`. All dependencies are injected (no module-level singletons inside agents). This agent can be slotted into a parent workspace-level agent's `sub_agents` list without any internal changes.

---

## 📁 Module Layout

```
poker_worker/
├── slack_bot.py                # Lambda entry: builds coordinator, runs it
├── event_bridge_trigger.py     # Deterministic weekly poll posting (no agent)
├── config.py                   # Constants + per-agent instruction strings
├── database.py                 # DynamoDB adapter (PokerDatabase)
├── settlement.py               # Pure domain: greedy debt algorithm + Venmo links
├── vision.py                   # Slack image download helper
├── utils.py                    # get_env() secret helper
├── logging_utils.py            # JSON structured logger
│
├── agents/
│   ├── coordinator.py          # build_poker_coordinator(deps) → LlmAgent
│   ├── settlement_agent.py     # build_settlement_agent(deps) → LlmAgent
│   ├── settlement_pipeline.py  # build_settlement_pipeline(deps) → SequentialAgent
│   ├── leaderboard_agent.py    # build_leaderboard_agent(deps) → LlmAgent
│   └── chat_agent.py           # build_chat_agent(deps) → LlmAgent
│
└── tools/
    ├── profile.py              # get_user_profile, register_player_venmo
    ├── settlement_tools.py     # calculate_poker_settlements, record_game_result,
    │                           #   find_recent_game, overwrite_game_result,
    │                           #   delete_game_result
    ├── leaderboard.py          # get_poker_leaderboard
    ├── slack_tools.py          # slack_recent_channel_history, slack_react,
    │                           #   create_slack_search_tool, get_file_contents,
    │                           #   is_bot_in_thread
    └── poll.py                 # get_weekly_poll_results
```

---

## 🗄 DynamoDB Schema

Single-table design (PK/SK):

| PK | SK | Purpose |
|---|---|---|
| `USER#<slack_id>` | `PROFILE` | Player registration |
| `GAME#<game_id>` | `RESULT` | Full game record with fingerprint |
| `STATS#<name>` | `GAME#<game_id>` | Per-player per-game net for leaderboard |
| `POLL#<week_id>` | `METADATA` | Weekly poll channel/ts/emoji mapping |

---

## ⚙️ Configuration

All per-agent instruction strings live in `config.py`:

| Constant | Used by |
|---|---|
| `BASE_PERSONALITY` | Shared prefix for all agent instructions |
| `COORDINATOR_INSTRUCTION` | PokerCoordinator routing rules |
| `SETTLEMENT_AGENT_INSTRUCTION` | SettlementAgent |
| `VISION_STEP_INSTRUCTION` | VisionStep (SequentialAgent) |
| `NAME_RESOLVER_STEP_INSTRUCTION` | NameResolverStep |
| `PERSIST_STEP_INSTRUCTION` | PersistStep |
| `FORMAT_STEP_INSTRUCTION` | FormatStep |
| `LEADERBOARD_AGENT_INSTRUCTION` | LeaderboardAgent |
| `CHAT_AGENT_INSTRUCTION` | ChatAgent |

Environment variables are managed via AWS Secrets Manager and Terraform. Use `make secrets` to sync them locally.

---

## 🧪 Local Setup

### 1. Sync Secrets
```bash
make secrets
```

### 2. Running the Stack
```bash
make local
```

### 3. Manual Development
1. Start DynamoDB: `docker-compose -f docker/docker-compose.yml up dynamodb-local`
2. Initialize schema: `make init-db`
3. Run bridge: `python dev/local_bridge.py`

### 4. Testing
```bash
make test
```

Trigger a manual poll event:
```bash
curl -X POST http://localhost:5000/trigger-poll
```

---

## 🚢 CI/CD & Deployment

### Packaging
```bash
make build
```

### Terraform
```bash
make deploy
make destroy
```
