# PokerBot

PokerBot is a Slack assistant designed for private poker groups. It manages weekly game polls and helps players settle debts by analyzing screenshots from the Pokerrrr 2 app using Google Gemini 2.5 Flash.

## Core Features

- **Weekly Polls:** Automatically triggers polls to schedule games.
- **Registration:** Maps Slack users to poker names and Venmo handles.
- **Vision Processing:** Extracts profit/loss data from app screenshots.
- **Settlement Logic:** Calculates the most efficient way to settle up (who pays whom).
- **Venmo Integration:** Generates one-click payment links.

## Project Structure

- `poker_worker/`: Core logic (Slack interactions, AI vision, database).
- `poker_handler/`: API Gateway entry point (signature verification and worker invocation).
- `main.tf`: Infrastructure defined via Terraform.
- `build.sh`: Packages Lambdas (uses Docker for binary compatibility).
- `deploy.sh`: Deploys to AWS.

## Quick Start

### Deployment

Deployment is managed via Terraform and requires the `compbot-dev` AWS profile.

1.  Ensure you have an AWS profile named `compbot-dev` in `~/.aws/credentials`.
2.  Run the build and deploy scripts:
    ```bash
    ./build.sh
    ./deploy.sh
    ```

For detailed local development and E2E testing instructions, see [DEVELOPER.md](DEVELOPER.md).
