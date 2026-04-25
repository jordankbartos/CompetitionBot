# 🃏 PokerBot

PokerBot is a Slack-based assistant tailored for private poker groups. It streamlines the "boring" parts of playing poker: scheduling games, tracking who owes whom, and generating easy payment links.

Powered by **AWS Lambda**, **DynamoDB**, and **Google Gemini 1.5 Flash**, PokerBot uses advanced AI vision to parse game results directly from screenshots.

---

## 🚀 Features

- **Automated Scheduling:** Triggers weekly reaction-based polls with randomized emojis to find the best night for a game.
- **Smart Registration:** Maps Slack users to their in-game poker names and Venmo handles.
- **AI-Powered Vision:** Just post a screenshot of the Pokerrrr 2 result screen, and PokerBot will extract everyone's profit/loss.
- **Optimized Settlements:** Calculates the minimum number of transactions needed to settle all debts.
- **One-Click Payments:** Generates Venmo deep links so you can pay your debts with a single tap.
- **AI Conversation:** Chat with PokerBot about the game or anything else – it knows the lingo.

---

## 🛠 Commands

Mention `@PokerBot` in any channel it's in to use these commands:

| Command | Description | Example |
| :--- | :--- | :--- |
| `register "Name" @Venmo` | Map your Slack ID to your poker name and Venmo handle. | `@PokerBot register "Doyle Brunson" @Doyle-Poker` |
| `settle up` | Post this along with a Pokerrrr 2 screenshot to calculate debts. | `@PokerBot settle up [attached image]` |
| `results` / `poll` | View the current emoji reaction tally for the weekly game poll. | `@PokerBot results` |
| `[anything else]` | Chat with PokerBot. It responds using Gemini AI. | `@PokerBot who is the biggest whale here?` |

---

## 🏗 Project Structure

- `poker_handler/`: Entry point Lambda that handles Slack signature verification and fast-ack.
- `poker_worker/`: Core logic Lambda (AI vision, settlement math, DB operations).
- `terraform/` (`main.tf`): Infrastructure as Code defining the AWS environment.
- `scripts/`: Utility scripts for local development and setup.

---

## 📦 Quick Start

### Prerequisites
- AWS Account with CLI configured (`compbot-dev` profile).
- Docker (for building Lambda-compatible packages).
- Python 3.12.

### Deploy to AWS
1. **Build:** Package the Lambda functions:
   ```bash
   ./build.sh
   ```
2. **Deploy:** Apply Terraform changes:
   ```bash
   ./deploy.sh
   ```

For deep dives into the architecture and local development setup, see [DEVELOPER.md](DEVELOPER.md).
