import asyncio
import random
from typing import List
from web3 import Web3, HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
import sys
from dataclasses import dataclass
from colorama import init, Fore, Style


init(autoreset=True)


@dataclass
class NetworkConfig:
    name: str = "Pharos Testnet"
    chain_id: int = 688689
    rpc_url: str = "https://atlantic.dplabs-internal.com"
    currency_symbol: str = "PHRS"


@dataclass
class WalletData:
    address: str
    private_key: str

class PharosClient:
    def __init__(self):
        self.network = NetworkConfig()
        self.w3 = Web3(HTTPProvider(self.network.rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def load_wallets(self) -> List[WalletData]:
        """Load wallets from pkey.txt"""
        try:
            with open("pkey.txt", "r") as f:
                lines = f.readlines()
            wallets = []
            for line in lines:
                line = line.strip()
                if line and ":" in line:
                    address, private_key = line.split(":")
                    wallets.append(WalletData(address.strip(), private_key.strip()))
            if not wallets:
                print(f"{Fore.RED}ERROR: No valid wallets found in pkey.txt{Style.RESET_ALL}")
                sys.exit(1)
            return wallets
        except FileNotFoundError:
            print(f"{Fore.RED}ERROR: pkey.txt not found{Style.RESET_ALL}")
            sys.exit(1)
        except Exception as e:
            print(f"{Fore.RED}ERROR: Error loading wallets: {str(e)}{Style.RESET_ALL}")
            sys.exit(1)

    def load_receivers(self) -> List[str]:
        """Load receiver addresses from receiver_address.txt"""
        try:
            with open("receiver_address.txt", "r") as f:
                addresses = [line.strip() for line in f.readlines() if line.strip()]
            if not addresses:
                print(f"{Fore.RED}ERROR: No receiver addresses found in receiver_address.txt{Style.RESET_ALL}")
                sys.exit(1)
            return addresses
        except FileNotFoundError:
            print(f"{Fore.RED}ERROR: receiver_address.txt not found{Style.RESET_ALL}")
            sys.exit(1)
        except Exception as e:
            print(f"{Fore.RED}ERROR: Error loading receiver addresses: {str(e)}{Style.RESET_ALL}")
            sys.exit(1)

    async def transfer_phrs(self, wallet: WalletData, receiver_address: str) -> bool:
        """Transfer maximum PHRS balance to receiver address (no receipt waiting)"""
        try:
            account = self.w3.eth.account.from_key(wallet.private_key)
            balance = self.w3.eth.get_balance(wallet.address)
            
            if balance == 0:
                print(f"{Fore.YELLOW}WARNING: No balance in wallet {wallet.address}{Style.RESET_ALL}")
                return False

            
            gas_limit = 21000
            gas_price = self.w3.eth.gas_price
            max_fee = gas_limit * gas_price
            amount = balance - max_fee

            if amount <= 0:
                print(f"{Fore.YELLOW}WARNING: Insufficient balance after gas fees for {wallet.address}{Style.RESET_ALL}")
                return False

            
            tx = {
                "to": self.w3.to_checksum_address(receiver_address),
                "value": amount,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "nonce": self.w3.eth.get_transaction_count(wallet.address),
                "chainId": self.network.chain_id
            }

            
            signed_tx = self.w3.eth.account.sign_transaction(tx, wallet.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            
            print(f"{Fore.GREEN}SUCCESS: Sent from {wallet.address} → {receiver_address}")
            print(f"{Fore.CYAN}Explorer: https://atlantic.pharosscan.xyz/tx/{self.w3.to_hex(tx_hash)}{Style.RESET_ALL}")
            return True

        except Exception as e:
            print(f"{Fore.RED}ERROR: Transfer failed for {wallet.address}: {str(e)}{Style.RESET_ALL}")
            return False

    async def process_wallet(self, wallet: WalletData, receivers: List[str]):
        """Process transfers for a single wallet"""
        print(f"{Fore.CYAN}INFO: Processing wallet: {wallet.address}{Style.RESET_ALL}")
        receiver = random.choice(receivers)
        await self.transfer_phrs(wallet, receiver)

    async def run(self):
        """Process all wallets once and exit"""
        wallets = self.load_wallets()
        receivers = self.load_receivers()
        
        print(f"{Fore.CYAN}INFO: Starting transfer for all wallets{Style.RESET_ALL}")
        for wallet in wallets:
            await self.process_wallet(wallet, receivers)
        
        print(f"{Fore.GREEN}SUCCESS: All wallet transfers completed!{Style.RESET_ALL}")

async def main():
    client = PharosClient()
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())
