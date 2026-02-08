# 🤖 AGENTS.md

This guide is for agentic coding agents (like yourself) working in the PokerBot repository. Adhere to these standards to ensure consistency and safety.

## 🛠 Project Commands

### Build & Deploy
- **Build Package:** `./build.sh` (Packages Lambdas using Docker for binary compatibility).
- **Deploy to AWS:** `./deploy.sh` (Runs Terraform apply).
- **Destroy Infra:** `./destroy.sh` (Runs Terraform destroy).
- **CRITICAL:** All dependencies with C-extensions (e.g., `grpcio`, `cryptography`) **MUST** be built using the Dockerized environment in `build.sh`. Never run `pip install` directly for deployment purposes. `boto3` is provided by the Lambda runtime; do not include it in `requirements.txt`.

### Local Development
- **Environment:** Development is managed with **Conda** (env: `slackbot`). Verify the environment is active before starting work.
- **Initialize DB:** `python scripts/init_local_db.py` (Creates table schema in DynamoDB Local).
- **Start Local Bridge:** `python local_bridge.py` (Flask server mimicking AWS Lambda).
- **Docker Compose:** Prefer `docker-compose up` for local E2E testing to ensure parity (includes `dynamodb-local`, `bridge`, and `ngrok`).
- **Expose Locally:** `ngrok http 5000` (Use for Slack webhook integration).
- **Trigger Poll:** `curl -X POST http://localhost:5000/trigger-poll` (Manually fires the scheduler).
- **Environment Variables:** Local dev uses a `.env` file. Do not commit this file. See `fetch_secrets.sh` for how to pull production values for local testing.

### Testing Strategy
- **Unit Tests:** Focus on domain logic (e.g., `settlement.py`). These should have zero external dependencies.
- **Integration Tests:** Test the interaction between domain logic and the database wrapper. Use DynamoDB Local or the Docker Compose stack.
- **Mocking:** Use `unittest.mock` to mock Slack API calls or Gemini AI responses.
- **Test Discovery:** Ensure all tests are in the `tests/` directory and follow the `test_*.py` naming pattern.
- **Test Coverage:** Aim for high coverage in the `Domain` layer. Infrastructure and Adapters can be covered by integration tests.
- **Continuous Verification:** After making changes, run `ruff check .` to ensure no linting regressions.

---

## 🎨 Code Style & Philosophy

### Clean Code Principles
- **Self-Documenting Code:** Prioritize clarity in naming and structure so the code's intent is obvious without comments. If the code is hard to read, refactor it.
- **Single Responsibility Principle (SRP):** Every module, class, and function must have exactly one reason to change. 
    - A function should do one thing and do it well. 
    - A class should represent one concept. 
    - A module should group related responsibilities.
- **Descriptive Naming:** 
    - Use highly descriptive names for variables, functions, classes, and modules. 
    - Avoid abbreviations unless they are industry standard (e.g., `id`, `url`).
    - *Exception:* Short names (e.g., `i`, `j`) are acceptable only for short-lived loop iterators.
- **Avoid Comments:** Do not use comments to explain *what* the code is doing. If a comment is needed to explain the logic, refactor the code to be more self-documenting. Only use comments for high-level "why" decisions that cannot be expressed in code or to document complex algorithms that are inherently non-obvious.
- **Dry (Don't Repeat Yourself):** Abstract common logic into reusable functions or utilities. Avoid "WET" (Write Everything Twice) code.
- **Formatting:** Adhere to the `ruff` default style. No trailing whitespace, one newline at the end of files.

### Python Conventions (Target: 3.12)
- **Formatting:** 4 spaces per indent. Max line length: 100 characters.
- **Naming:**
  - `snake_case`: Variables, functions, and module names.
  - `PascalCase`: Class names.
  - `UPPER_SNAKE_CASE`: Constants and environment variables.
- **Typing:** Use Python type hints (e.g., `def func(id: str) -> bool:`) for all new functions. Ensure types are as specific as possible (use `list[str]` instead of `list`).
- **Imports:** 
  1. Standard library imports.
  2. Third-party library imports (e.g., `boto3`, `slack_sdk`).
  3. Local module imports (e.g., `from database import PokerDatabase`).
  *Note: Always use absolute imports for local modules.*
- **Docstrings:** Use triple quotes `"""` to document function purpose, parameters, and return values. This is critical for tools exposed to the LLM agent. Use Google-style or Sphinx-style docstrings consistently.

---

## 🏗 Architectural Patterns & Clean Architecture

### Reusability and Extensibility
The codebase follows **Clean Architecture** to ensure it can grow and adapt:
- **Layers of Concern:** 
    - **Infrastructure:** AWS Lambda handlers, DynamoDB client, Slack SDK.
    - **Adapters:** `agent_tools.py` and `database.py`. These bridge the gap between infra and domain.
    - **Domain:** Pure business logic like `settlement.py`.
- **Decoupling:** Business logic must not know about Slack or AWS. It should take raw data (dicts, lists, primitives) and return results.
- **Dependency Injection:** Pass dependencies (like database clients or configuration) into functions or classes rather than hardcoding global instances. This makes testing significantly easier.
- **Abstraction:** Use abstract base classes or protocols if you anticipate needing multiple implementations (e.g., switching from Gemini to another LLM).
- **Secrets:** Use `utils.get_env()` to access environment variables. It handles both raw strings and JSON-encoded secrets from AWS Secrets Manager.

### 1. Lambda Separation
- **`poker_handler/`**: Lightweight entry point. 
    - Performs Slack signature verification.
    - Handles Slack URL verification (challenge).
    - Returns a `200 OK` immediately (Fast-Ack) to prevent Slack retry loops.
    - Triggers the worker Lambda asynchronously.
- **`poker_worker/`**: Core orchestrator. 
    - Triggered by the handler or EventBridge.
    - Manages stateful conversations using the LLM (Gemini).
    - Dispatches work to specialized domain services.

### 2. DynamoDB Single-Table Design
We use a single table for all data. Query patterns:
- **User Profile:** `PK: USER#<slack_id>`, `SK: PROFILE`. Used for registration and lookup.
- **Game Results:** `PK: GAME#<game_id>`, `SK: RESULT`. Stores full game JSON and metadata.
- **User Stats:** `PK: STATS#<lowercase_name>`, `SK: GAME#<game_id>`. Used for calculating leaderboards and player history.
- **Poll Metadata:** `PK: POLL#<week_id>`, `SK: METADATA`. Tracks the current week's scheduling poll.

### 3. Domain Services & Tools
- **Atomic Operations:** Tools in `agent_tools.py` should be atomic. If a task requires multiple steps (e.g., settle and record), the agent should call multiple tools or the tool should be carefully composed.
- **Input Validation:** Tools must validate their inputs. Since they are called by an LLM, assume inputs might be slightly malformed or unexpected.

---

## 🚀 Workflow Examples

### Example: Adding a New Feature
1.  **Define Logic:** Implement core logic in a domain module (e.g., `poker_worker/settlement.py`).
2.  **Expose Tool:** Add a corresponding tool in `agent_tools.py`.
3.  **Test E2E:** Use `docker-compose up` and the `local_bridge.py` workflow.
4.  **Verify UI:** Check extraction/responses via the Slack integration (ngrok).

### Example: Updating Infrastructure
1.  **Modify Terraform:** Update `main.tf` (resources use `poker_` prefix).
2.  **Deploy:** Run `./deploy.sh`.
3.  **Update Docs:** If the change affects behavior, update `README.md` or `DEVELOPER.md`.

---

## 💡 Agent Instructions
1. **Be Proactive:** If you add a new database field, update the corresponding `PokerDatabase` methods and ensure `agent_tools.py` can expose it.
2. **Consult Docs:** Always read `DEVELOPER.md` before making architectural changes.
3. **Git Hygiene:** NEVER commit or push changes automatically. Verify changes first, then request explicit approval.
4. **Documentation:** ALWAYS update relevant docs when implementing features or changing existing behavior.
5. **Safety:** Never hardcode secrets. Use environment variables that map to AWS Secrets Manager via `utils.get_env()`.
6. **Idempotency:** Ensure game recording and registration are idempotent (check `fingerprint` in `record_game_result`).
7. **Error Handling:** Always use `try...except` blocks around external service calls and log the exception with context.

