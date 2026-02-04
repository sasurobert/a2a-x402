import unittest
import os
import time
import pytest
from multiversx_sdk import (
    Account,
    Mnemonic,
    ApiNetworkProvider,
    NetworkEntrypoint,
    TransactionsFactoryConfig,
    TransferTransactionsFactory
)
from x402_a2a.schemes.multiversx import MultiversXScheme
from x402_a2a.schemes.multiversx_config import MultiversXConfig

# Skips if no mnemonic provided
@pytest.mark.integration
class TestRealDevnet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mnemonic_str = os.getenv("MVX_TEST_MNEMONIC")
        if not cls.mnemonic_str:
            raise unittest.SkipTest("MVX_TEST_MNEMONIC not set")
            
        cls.chain_id = "D"
        cls.api_url = "https://devnet-api.multiversx.com"
        cls.provider = ApiNetworkProvider(cls.api_url)
        
        # Setup Account
        cls.mnemonic = Mnemonic.from_string(cls.mnemonic_str)
        cls.account = Account.new_from_mnemonic(cls.mnemonic.get_text())
        
        # Sync nonce
        try:
            cls.account.nonce = cls.provider.get_account(cls.account.address).nonce
        except Exception as e:
            print(f"Failed to sync nonce: {e}")
            cls.account.nonce = 0

    def test_payment_flow(self):
        """
        Tests the full flow:
        1. Merchant (Scheme) creates requirements
        2. Client signs transaction
        3. Client broadcasts (simulated here)
        4. Merchant verifies
        """
        # 1. Merchant creates requirements
        scheme = MultiversXScheme(chain_id=self.chain_id)
        # Use a random receiver (or self)
        receiver = self.account.address
        amount = 100000000000000000 # 0.1 EGLD
        
        req = scheme.create_payment_requirements(
            amount=amount,
            token_identifier="EGLD",
            receiver=receiver.bech32(),
            description="Integration Test Payment"
        )
        
        self.assertEqual(req.scheme, "mvx")
        self.assertEqual(req.network, f"mvx:{self.chain_id}")
        
        # 2. Client constructs payment
        # Note: In real A2A, the client uses their own signer.
        # Here we simulate the client using the test account.
        
        class TestSigner:
            def __init__(self, account):
                self.account = account
            def sign_transaction(self, tx):
                return self.account.sign_transaction(tx)
                
        signer = TestSigner(self.account)
        
        payload = scheme.construct_payment_payload(
            requirements=req,
            signer=signer,
            sender_address=self.account.address.bech32(),
            nonce=self.account.nonce
        )
        
        # 3. Broadcast (Simulate network propagation)
        # The payload contains the signed tx signature. 
        # But `construct_payment_payload` returns a `PaymentPayload` object with dict.
        # We need to reconstruct the SDK Transaction object to broadcast it using ApiNetworkProvider,
        # OR use the provider's `send_transaction` if we had the object.
        # Typically the client would broadcast.
        
        # Reconstruct for broadcast
        from multiversx_sdk import Transaction
        
        tx_data_dict = payload.payload 
        # Note: payload.payload is a dict built in `multiversx.py`
        
        tx = Transaction(
            nonce=tx_data_dict["nonce"],
            value=tx_data_dict["value"],
            receiver=Account.new_from_bech32(tx_data_dict["receiver"]).address,
            sender=Account.new_from_bech32(tx_data_dict["sender"]).address,
            gas_price=tx_data_dict["gasPrice"],
            gas_limit=tx_data_dict["gasLimit"],
            data=tx_data_dict.get("data", "").encode(),
            chain_id=tx_data_dict["chainID"],
            version=tx_data_dict["version"]
        )
        tx.signature = bytes.fromhex(tx_data_dict["signature"])
        
        try:
            tx_hash = self.provider.send_transaction(tx)
            print(f"Transaction sent: {tx_hash}")
            self.assertIsNotNone(tx_hash)
            
            # 4. Verify (Merchant side)
            # In a real scenario, we wait for processing.
            # verify_transaction_content checks logic, not on-chain status yet.
            
            # Mock tx data coming from API for verification check
            simulated_api_response = {
                "receiver": tx.receiver.bech32(),
                "sender": tx.sender.bech32(),
                "data": tx.data.decode() if tx.data else "",
                "status": "success" # We pretend it succeeded
            }
            
            is_valid = scheme.verify_transaction_content(simulated_api_response, req)
            self.assertTrue(is_valid)
            
        except Exception as e:
            self.fail(f"Broadcast/Verification failed: {e}")

if __name__ == "__main__":
    unittest.main()
