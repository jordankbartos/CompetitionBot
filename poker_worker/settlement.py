"""
Domain logic for poker game settlements and external links.
This module contains pure business logic and should not have external dependencies.
"""

import logging

logger = logging.getLogger(__name__)


def calculate_settlements(player_data: dict[str, float]) -> list[tuple[str, str, float]]:
    """
    Calculates the most efficient way to settle debts between players.

    Args:
        player_data: A dictionary mapping player names to their net profit/loss.
                    Positive values are winners, negative are losers.

    Returns:
        A list of tuples in the format (debtor, creditor, amount).
    """
    # Separate winners and losers
    winners = []
    losers = []

    for name, amount in player_data.items():
        if amount > 0:
            winners.append({"name": name, "amount": amount})
        elif amount < 0:
            losers.append({"name": name, "amount": abs(amount)})

    # Sort to optimize (largest-to-largest reduces number of transactions)
    winners.sort(key=lambda x: x["amount"], reverse=True)
    losers.sort(key=lambda x: x["amount"], reverse=True)

    settlements = []
    w_idx = 0
    l_idx = 0

    while w_idx < len(winners) and l_idx < len(losers):
        winner = winners[w_idx]
        loser = losers[l_idx]

        # Determine the amount to transfer
        transfer = min(winner["amount"], loser["amount"])

        if transfer > 0:
            # Rounded to 2 decimal places for financial accuracy
            settlements.append((loser["name"], winner["name"], round(float(transfer), 2)))

        # Update remaining amounts
        winner["amount"] -= transfer
        loser["amount"] -= transfer

        # Move to next if amount is settled
        if winner["amount"] <= 0:
            w_idx += 1
        if loser["amount"] <= 0:
            l_idx += 1

    return settlements


def generate_venmo_link(handle: str, amount: float, note: str = "Poker") -> str:
    """
    Generates a Venmo deep link for a payment.

    Args:
        handle: The Venmo handle of the recipient (e.g., '@username').
        amount: The dollar amount to pay.
        note: The transaction note.

    Returns:
        A URL string formatted as a Venmo deep link.
    """
    clean_handle = handle.replace("@", "")
    return f"venmo://paycharge?txn=pay&recipients={clean_handle}&amount={amount:.2f}&note={note}"
