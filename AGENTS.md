# 🤖 AGENTS.md

This guide is for agentic coding agents (like yourself) working in the PokerBot repository. Adhere to these standards to ensure consistency, testability, and safety.

## 🛠 Project Commands

We use a `Makefile` to centralize common tasks. Prefer these commands over calling scripts directly.

### Build & Deploy
- **Build Package:** `make build` (Calls `scripts/build.sh`, uses Docker for binary compatibility).
- **Deploy to AWS:** `make deploy` (Runs Terraform from `infra/`).
- **Destroy Infra:** `make destroy` (Runs Terraform destroy).
- **CRITICAL:** Dependencies with C-extensions MUST be built using the Dockerized environment in `build.sh`. Never run `pip install` directly for deployment.

### Local Development
- **Environment:** Development is managed with **Conda** (env: `slackbot`).
- **Run Everything:** `make local` (Runs `docker-compose` for DynamoDB, schema, bridge, ngrok).
- **Start Local Bridge:** `python dev/local_bridge.py`
- **Fetch Secrets:** `make secrets` (Pulls prod values into `.env`).
- **Trigger Poll:** `curl -X POST http://localhost:5000/trigger-poll`

### 🧪 Testing Strategy & Agentic TDD
Agents must follow Test-Driven Development (TDD) workflows. Write failing tests first to establish clear requirements before modifying business logic.

- **Run All Tests:** `make test` (Runs `python3 -m unittest discover tests`).
- **Run a Single Test Class:** `python3 -m unittest tests.test_settlement.TestSettlement`
- **Run a Specific Test Method:** `python3 -m unittest tests.test_settlement.TestSettlement.test_even_split`
- **Linting & Types:** `ruff check .` (Must pass without warnings after changes).

**Test Quality Requirements:**
- **Meaningful Assertions:** Tests must validate real domain constraints. Trivial tests (e.g., `assert 3 == 3` or testing standard library features) are strictly forbidden.
- **Mocking:** Use `unittest.mock` strictly for boundaries (Slack API, Gemini API, DB wrappers). Never mock domain logic.
- **Isolation:** Tests must not depend on global state or execution order.

---

## 🏗 Architectural Patterns

This project follows **Clean Architecture**:
- **Domain:** Pure business logic (`domain/` or `settlement.py`). **No external dependencies allowed.**
- **Adapters:** External boundary interfaces (`agent_tools.py`, `database.py`).
- **Infrastructure:** AWS Lambda handlers, DynamoDB clients, Slack SDK.
- **Dependency Injection:** Pass dependencies/data as arguments; avoid hardcoding global instances.

---

## 🎨 Code Style & Philosophy

### 1. Common Sense & Clean Code
- **KISS & SRP:** Keep it simple. Every function, class, and module must have a Single Responsibility. If a function is doing two things, split it.
- **DRY:** Abstract repeated logic cleanly, but prioritize readability over premature optimization.
- **Function Scope & Length:** Functions should be small (ideally < 20 lines) and operate at a single level of abstraction.
- **Self-Documenting Code:** Rely on descriptive, explicit naming (`calculate_user_debt()` over `calc_ud()`).
- **No Junk Comments:** Do not write comments explaining *what* code does (the code should tell you that). Only use comments to explain *why* a specific, non-obvious technical decision was made.

### 2. Functional Programming Practices
Maximize testability and maintainability by utilizing functional paradigms where possible:
- **Pure Functions:** Functions should avoid side effects and always return the same output for a given input. Keep domain logic functionally pure.
- **Immutability:** Avoid mutating arguments in-place. Prefer returning new data structures (e.g., list comprehensions, copies).
- **Data over Objects:** Prefer simple `dataclasses`, `NamedTuples`, or standard dicts for data transfer rather than heavy stateful object instances.

### 3. Python 3.12 Conventions
- **Formatting:** 4 spaces per indent. Max line length: 100 characters. Adhere to `ruff` standard formatting.
- **Naming:**
  - `snake_case` for variables and functions.
  - `PascalCase` for classes.
  - `UPPER_SNAKE_CASE` for constants.
- **Typing:** Explicit type hints are mandatory for all new function arguments and return types.
- **Imports:** 1. Standard Library, 2. Third-party, 3. Local/Project. Use absolute imports.
- **Error Handling:** Avoid silent failures. Catch specific exceptions, not broad `Exception` blocks. Log errors with context and re-raise if the function cannot handle them meaningfully. Use `try...except` generously around external IO boundaries.

---

## 💡 Workflow Mandates for Agents
1. **Think First:** Consult this document and `DEVELOPER.md` before making architectural changes.
2. **TDD Loop:** Red -> Green -> Refactor. Write the test, make it pass, run `ruff check .`, refactor.
3. **Safety First:** NEVER commit secrets. Use `utils.get_env()`.
4. **Git Hygiene:** Only commit when explicitly asked by the user. Do not push automatically.
5. **Idempotency:** Ensure database and external state operations are idempotent.
