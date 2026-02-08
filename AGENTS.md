# 🤖 AGENTS.md

This guide is for agentic coding agents (like yourself) working in the PokerBot repository. Adhere to these standards to ensure consistency and safety.

## 🛠 Project Commands

We use a `Makefile` to centralize common tasks. Prefer these commands over calling scripts directly.

### Build & Deploy
- **Build Package:** `make build` (Calls `scripts/build.sh`, uses Docker for binary compatibility).
- **Deploy to AWS:** `make deploy` (Runs Terraform from `infra/`).
- **Destroy Infra:** `make destroy` (Runs Terraform destroy).
- **CRITICAL:** All dependencies with C-extensions (e.g., `grpcio`, `cryptography`) **MUST** be built using the Dockerized environment in `build.sh`. Never run `pip install` directly for deployment purposes. `boto3` is provided by the Lambda runtime; do not include it in `requirements.txt`.

### Local Development
- **Environment:** Development is managed with **Conda** (env: `slackbot`). Verify the environment is active before starting work.
- **Initialize DB:** `make init-db` (Calls `scripts/init_local_db.py`).
- **Start Local Bridge:** `python dev/local_bridge.py` (Flask server mimicking AWS Lambda).
- **Docker Compose:** `make local` (Runs `docker-compose -f docker/docker-compose.yml up`). Includes `dynamodb-local`, `bridge`, and `ngrok`.
- **Fetch Secrets:** `make secrets` (Pulls production values for local testing into `.env`).
- **Trigger Poll:** `curl -X POST http://localhost:5000/trigger-poll` (Manually fires the scheduler).

### Testing Strategy
- **Unit Tests:** `make test` (Runs `python3 -m unittest discover tests`). Focus on domain logic (e.g., `settlement.py`).
- **Integration Tests:** Test the interaction between domain logic and the database wrapper. Use DynamoDB Local or the Docker Compose stack.
- **Mocking:** Use `unittest.mock` to mock Slack API calls or Gemini AI responses.
- **Test Discovery:** Ensure all tests are in the `tests/` directory and follow the `test_*.py` naming pattern.
- **Continuous Verification:** After making changes, run `ruff check .` to ensure no linting regressions.

---

## 🎨 Project Structure

- **`poker_handler/`**: Lightweight entry point (Security & Fast-Ack).
- **`poker_worker/`**: Core orchestrator and agent logic.
- **`domain/`**: Pure business logic (currently inside `poker_worker/` as `settlement.py`).
- **`infra/`**: Terraform configuration and state.
- **`dev/`**: Local development utilities (bridge, zip tools).
- **`docker/`**: Docker Compose and Dockerfile for local development.
- **`scripts/`**: Build, deployment, and database utility scripts.

---

## 🎨 Code Style & Philosophy

### Clean Code Principles
- **Self-Documenting Code:** Prioritize clarity in naming and structure. If the code is hard to read, refactor it.
- **Single Responsibility Principle (SRP):** Every module, class, and function must have exactly one reason to change.
- **Descriptive Naming:** Use highly descriptive names. Avoid abbreviations unless standard.
- **Avoid Comments:** Do not explain *what* the code is doing. Only explain *why* for non-obvious decisions.
- **Dry (Don't Repeat Yourself):** Abstract common logic. Avoid "WET" code.
- **Formatting:** Adhere to `ruff` default style.

### Python Conventions (Target: 3.12)
- **Formatting:** 4 spaces per indent. Max line length: 100 characters.
- **Naming:** `snake_case` for vars/funcs, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- **Typing:** Use Python type hints for all new functions.
- **Imports:** 1. Standard, 2. Third-party, 3. Local. Use absolute imports.
- **Docstrings:** Use triple quotes `"""` with Google-style documentation for all public functions and classes.

---

## 🏗 Architectural Patterns & Clean Architecture

### Reusability and Extensibility
The codebase follows **Clean Architecture**:
- **Infrastructure:** AWS Lambda handlers, DynamoDB client, Slack SDK.
- **Adapters:** `agent_tools.py` and `database.py`.
- **Domain:** Pure business logic (e.g., `settlement.py`). **No external dependencies allowed here.**
- **Decoupling:** Business logic must not know about Slack or AWS.
- **Dependency Injection:** Pass dependencies into functions rather than hardcoding global instances.

---

## 💡 Agent Instructions
1. **Be Proactive:** If you add a new database field, update `PokerDatabase` and `agent_tools.py`.
2. **Consult Docs:** Always read `DEVELOPER.md` before making architectural changes.
3. **Git Hygiene:** NEVER commit or push changes automatically.
4. **Safety:** Never hardcode secrets. Use `utils.get_env()`.
5. **Idempotency:** Ensure game recording is idempotent using fingerprints.
6. **Error Handling:** Use `try...except` around external calls and log with context.
