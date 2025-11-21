import os
import time
import random
from web3 import Web3
import requests
from decimal import Decimal

# Network configuration
NETWORK_CONFIG = {
    "name": "Pharos Testnet",
    "chain_id": 688689,
    "rpc_url": "https://atlantic.dplabs-internal.com",
    "currency_symbol": "PHRS",
    "explorer_url": "https://atlantic.pharosscan.xyz/tx/"
}

# Colors for console output
class Colors:
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'
    WHITE = '\033[37m'
    BOLD = '\033[1m'

class Logger:
    @staticmethod
    def info(msg):
        print(f"{Colors.GREEN}[✓] {msg}{Colors.RESET}")
    
    @staticmethod
    def wallet(msg):
        print(f"{Colors.YELLOW}[➤] {msg}{Colors.RESET}")
    
    @staticmethod
    def warn(msg):
        print(f"{Colors.YELLOW}[!] {msg}{Colors.RESET}")
    
    @staticmethod
    def error(msg):
        print(f"{Colors.RED}[✗] {msg}{Colors.RESET}")
    
    @staticmethod
    def success(msg):
        print(f"{Colors.GREEN}[+] {msg}{Colors.RESET}")
    
    @staticmethod
    def loading(msg):
        print(f"{Colors.CYAN}[⟳] {msg}{Colors.RESET}")
    
    @staticmethod
    def step(msg):
        print(f"{Colors.WHITE}[➤] {msg}{Colors.RESET}")
    
    @staticmethod
    def banner():
        print(f"{Colors.CYAN}{Colors.BOLD}")
        print("-------------------------------------------------")
        print("      Pharos Testnet Bulk Transfer")
        print("-------------------------------------------------")
        print(f"{Colors.RESET}")

def load_private_keys():
    """Load private keys from main_key.txt"""
    try:
        with open("main_key.txt", "r") as f:
            private_keys = [line.strip() for line in f if line.strip()]
        return private_keys
    except FileNotFoundError:
        Logger.error("main_key.txt file not found!")
        return []

def load_recipient_addresses():
    """Load recipient addresses from address.txt"""
    try:
        with open("address.txt", "r") as f:
            addresses = [line.strip() for line in f if line.strip()]
        return addresses
    except FileNotFoundError:
        Logger.error("address.txt file not found!")
        return []

def setup_web3():
    """Setup Web3 connection to Pharos Testnet"""
    try:
        w3 = Web3(Web3.HTTPProvider(NETWORK_CONFIG["rpc_url"]))
        
        # Add POA middleware if available (for older web3 versions)
        try:
            from web3.middleware import geth_poa_middleware
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            Logger.info("POA middleware injected")
        except ImportError:
            Logger.warn("geth_poa_middleware not available, continuing without it")
        
        if w3.is_connected():
            Logger.success(f"Connected to {NETWORK_CONFIG['name']}")
            Logger.info(f"Chain ID: {w3.eth.chain_id}")
            Logger.info(f"Latest Block: {w3.eth.block_number}")
            return w3
        else:
            Logger.error("Failed to connect to network")
            return None
    except Exception as e:
        Logger.error(f"Web3 setup failed: {e}")
        return None

def get_transfer_amount():
    """Get transfer amount from user input"""
    while True:
        try:
            amount_input = input(f"\n{Colors.WHITE}[➤] Enter PHRS amount to send to each address: {Colors.RESET}").strip()
            amount = Decimal(amount_input)
            if amount <= 0:
                Logger.error("Amount must be greater than 0")
                continue
            return amount
        except ValueError:
            Logger.error("Please enter a valid number")

def check_balance(w3, address):
    """Check PHRS balance of an address"""
    try:
        balance_wei = w3.eth.get_balance(address)
        balance_phrs = w3.from_wei(balance_wei, 'ether')
        return Decimal(str(balance_phrs))
    except Exception as e:
        Logger.error(f"Failed to check balance for {address}: {e}")
        return Decimal('0')

def get_gas_parameters(w3):
    """Get gas price and parameters"""
    try:
        # Try to get gas price from network
        gas_price = w3.eth.gas_price
        gas_price_gwei = w3.from_wei(gas_price, 'gwei')
        Logger.info(f"Current gas price: {float(gas_price_gwei):.2f} Gwei")
        return gas_price
    except Exception as e:
        Logger.warn(f"Failed to get gas price, using default: {e}")
        # Use reasonable default for Pharos testnet
        return w3.to_wei('0.1', 'gwei')

def calculate_gas_cost(w3, gas_price, gas_limit=21000):
    """Calculate gas cost in PHRS"""
    gas_cost_wei = gas_price * gas_limit
    gas_cost_phrs = w3.from_wei(gas_cost_wei, 'ether')
    return Decimal(str(gas_cost_phrs))

def send_transaction(w3, private_key, to_address, amount_phrs):
    """Send PHRS transaction"""
    try:
        # Create account from private key
        account = w3.eth.account.from_key(private_key)
        from_address = account.address
        
        # Convert amount to wei (using Decimal for precision)
        amount_wei = w3.to_wei(float(amount_phrs), 'ether')
        
        # Check balance
        balance = check_balance(w3, from_address)
        Logger.info(f"Sender balance: {float(balance):.6f} PHRS")
        
        if balance < amount_phrs:
            Logger.error(f"Insufficient balance: {float(balance):.6f} < {float(amount_phrs)}")
            return None
        
        # Get gas parameters
        gas_price = get_gas_parameters(w3)
        
        # Standard gas limit for simple transfers
        gas_limit = 21000
        
        # Calculate total cost using Decimal for precision
        gas_cost_phrs = calculate_gas_cost(w3, gas_price, gas_limit)
        total_cost_phrs = amount_phrs + gas_cost_phrs
        
        Logger.info(f"Transfer amount: {float(amount_phrs):.6f} PHRS")
        Logger.info(f"Gas cost: {float(gas_cost_phrs):.6f} PHRS")
        Logger.info(f"Total cost: {float(total_cost_phrs):.6f} PHRS")
        
        if balance < total_cost_phrs:
            Logger.error(f"Insufficient balance for transaction + gas: {float(balance):.6f} < {float(total_cost_phrs):.6f}")
            return None
        
        # Build transaction
        nonce = w3.eth.get_transaction_count(from_address)
        
        transaction = {
            'to': to_address,
            'value': amount_wei,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': NETWORK_CONFIG["chain_id"]
        }
        
        # Sign transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, private_key)
        
        # Send transaction
        Logger.loading(f"Sending {float(amount_phrs):.6f} PHRS to {to_address}...")
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        tx_hash_hex = tx_hash.hex()
        
        # Wait for transaction receipt with timeout
        Logger.loading("Waiting for transaction confirmation...")
        start_time = time.time()
        timeout = 120  # 2 minutes timeout
        
        while time.time() - start_time < timeout:
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if receipt is not None:
                    if receipt.status == 1:
                        Logger.success(f"Transaction successful: {tx_hash_hex}")
                        Logger.info(f"Explorer: {NETWORK_CONFIG['explorer_url']}{tx_hash_hex}")
                        return tx_hash_hex
                    else:
                        Logger.error(f"Transaction failed: {tx_hash_hex}")
                        return None
            except Exception:
                pass  # Receipt not available yet
            
            time.sleep(5)  # Check every 5 seconds
        
        Logger.warn(f"Transaction pending - check later: {tx_hash_hex}")
        Logger.info(f"Explorer: {NETWORK_CONFIG['explorer_url']}{tx_hash_hex}")
        return tx_hash_hex
            
    except Exception as e:
        Logger.error(f"Transaction failed: {str(e)}")
        return None

def validate_address(w3, address):
    """Validate Ethereum address"""
    try:
        return w3.is_address(address)
    except:
        return False

def main():
    """Main function"""
    Logger.banner()
    
    # Load private keys and addresses
    private_keys = load_private_keys()
    if not private_keys:
        Logger.error("Please create main_key.txt with your private keys")
        return
    
    recipient_addresses = load_recipient_addresses()
    if not recipient_addresses:
        Logger.error("Please create address.txt with recipient addresses")
        return
    
    # Get transfer amount
    amount_phrs = get_transfer_amount()
    
    # Setup Web3 connection
    w3 = setup_web3()
    if not w3:
        return
    
    # Validate recipient addresses
    valid_addresses = []
    for address in recipient_addresses:
        if validate_address(w3, address):
            valid_addresses.append(address)
        else:
            Logger.error(f"Invalid address: {address}")
    
    if not valid_addresses:
        Logger.error("No valid recipient addresses found!")
        return
    
    Logger.info(f"Loaded {len(private_keys)} private key(s)")
    Logger.info(f"Loaded {len(valid_addresses)} valid recipient address(es)")
    Logger.info(f"Amount to send: {float(amount_phrs)} PHRS per address")
    
    # Calculate total cost using Decimal
    total_phrs = amount_phrs * len(valid_addresses)
    Logger.warn(f"Total PHRS to be sent: {float(total_phrs)} PHRS")
    
    # Confirm before proceeding
    confirm = input(f"\n{Colors.YELLOW}[!] Continue? (y/n): {Colors.RESET}").strip().lower()
    
    if confirm != 'y':
        Logger.info("Operation cancelled")
        return
    
    # Process transfers for each private key
    successful_transfers = 0
    failed_transfers = 0
    
    for i, private_key in enumerate(private_keys, 1):
        Logger.wallet(f"Processing wallet {i}/{len(private_keys)}")
        
        account = w3.eth.account.from_key(private_key)
        sender_address = account.address
        Logger.info(f"Sender address: {sender_address}")
        
        # Check sender balance
        sender_balance = check_balance(w3, sender_address)
        if sender_balance < amount_phrs:
            Logger.error(f"Skipping wallet {i}: Insufficient balance ({float(sender_balance):.6f} PHRS)")
            failed_transfers += len(valid_addresses)
            continue
        
        # Send to each recipient
        wallet_success = 0
        for j, recipient in enumerate(valid_addresses, 1):
            Logger.step(f"Sending to recipient {j}/{len(valid_addresses)}: {recipient}")
            
            tx_hash = send_transaction(w3, private_key, recipient, amount_phrs)
            if tx_hash:
                successful_transfers += 1
                wallet_success += 1
            else:
                failed_transfers += 1
            
            # Add delay between transactions
            if j < len(valid_addresses):
                delay = random.uniform(3, 7)
                Logger.info(f"Waiting {delay:.1f} seconds before next transfer...")
                time.sleep(delay)
        
        Logger.success(f"Wallet {i} completed: {wallet_success}/{len(valid_addresses)} successful transfers")
        
        # Add delay between wallets
        if i < len(private_keys):
            delay = random.uniform(10, 20)
            Logger.info(f"Waiting {delay:.1f} seconds before next wallet...")
            time.sleep(delay)
    
    # Summary
    print(f"\n{Colors.CYAN}{Colors.BOLD}")
    print("-------------------------------------------------")
    print("                 SUMMARY")
    print("-------------------------------------------------")
    print(f"{Colors.RESET}")
    print(f"{Colors.GREEN}Successful transfers: {successful_transfers}{Colors.RESET}")
    print(f"{Colors.RED}Failed transfers: {failed_transfers}{Colors.RESET}")
    print(f"{Colors.CYAN}Total PHRS sent: {float(successful_transfers * amount_phrs)} PHRS{Colors.RESET}")
    
    Logger.success("All transfers completed!")

if __name__ == "__main__":
    main()
