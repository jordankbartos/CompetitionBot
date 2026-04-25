"""
Legacy test file — redirects to new per-module test files.

The original agent_tools.py has been split into poker_worker/tools/*.py modules.
Tests have been migrated to tests/test_tools/. This file is kept to ensure
`make test` continues to run the full suite via discovery.
"""

# This file is intentionally left empty.
# See tests/test_tools/ for the replacement test suite.
