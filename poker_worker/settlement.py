import logging

logger = logging.getLogger(__name__)

def calculate_settlements(player_data):
    """
    player_data: dict { 'Name': net_amount }
    Returns a list of tuples: (debtor, creditor, amount)
    """
    # Separate winners and losers
    winners = []
    losers = []
    
    for name, amount in player_data.items():
        if amount > 0:
            winners.append({'name': name, 'amount': amount})
        elif amount < 0:
            losers.append({'name': name, 'amount': abs(amount)})
            
    # Sort to optimize (optional, but good for largest-to-largest)
    winners.sort(key=lambda x: x['amount'], reverse=True)
    losers.sort(key=lambda x: x['amount'], reverse=True)
    
    settlements = []
    w_idx = 0
    l_idx = 0
    
    while w_idx < len(winners) and l_idx < len(losers):
        w = winners[w_idx]
        l = losers[l_idx]
        
        # Determine the amount to transfer
        transfer = min(w['amount'], l['amount'])
        
        if transfer > 0:
            settlements.append((l['name'], w['name'], transfer))
            
        # Update remaining amounts
        w['amount'] -= transfer
        l['amount'] -= transfer
        
        # Move to next if amount is settled
        if w['amount'] == 0:
            w_idx += 1
        if l['amount'] == 0:
            l_idx += 1
            
    return settlements

def generate_venmo_link(handle, amount, note="Poker"):
    # Venmo deep link format
    # venmo://paycharge?txn=pay&recipients=Handle&amount=10&note=Poker
    clean_handle = handle.replace('@', '')
    return f"venmo://paycharge?txn=pay&recipients={clean_handle}&amount={amount}&note={note}"
