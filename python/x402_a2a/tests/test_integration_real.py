# Copyright 2025 Google LLC
# integration test without mocks (except for network calls)

import unittest
from unittest.mock import MagicMock

# Import REAL x402 types
from x402.types import PaymentRequirements, PaymentPayload
from x402_a2a.schemes.multiversx import MultiversXScheme

# We still mock the SDK if it's not installed in the environment, OR we expect it to be there.
# The user asked to "install all packages". 
# The optional dependencies for mvx should be installed.
# If they fail to install (e.g. system issues), we might fallback, but the user said "install all".
# We will assume they are installed.

from multiversx_sdk_core import Transaction, Address
from multiversx_sdk_wallet import UserSigner

class TestMultiversXIntegration(unittest.TestCase):
    def test_end_to_end_flow(self):
        # 1. Initialize Scheme
        scheme = MultiversXScheme(chain_id="1")
        
        # 2. Create Requirements
        req = scheme.create_payment_requirements(
            amount=1000000, # 1 USDC
            token_identifier="USDC-c76f1f",
            receiver="erd1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq6gq4hu"
        )
        
        # Assertions on REAL types
        self.assertIsInstance(req, PaymentRequirements)
        self.assertEqual(req.scheme, "mvx")
        self.assertEqual(req.network, "mvx:1")
        
        # 3. Construct Payload
        # We need a dummy signer
        class DummySigner:
            def sign(self, message: bytes) -> bytes:
                return b"signature_bytes"
                
        signer = DummySigner()
        sender_addr = "erd1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq6gq4hu"
        
        payload = scheme.construct_payment_payload(
            requirements=req,
            signer=signer,
            sender_address=sender_addr,
            nonce=10
        )
        
        self.assertIsInstance(payload, PaymentPayload)
        
        # Payload is now a Pydantic model (MultiversXPayload), not a dict
        data = payload.payload.model_dump()
        self.assertEqual(data["nonce"], 10)
        self.assertEqual(data["signature"], "7369676e61747572655f6279746573") # hex("signature_bytes")

if __name__ == '__main__':
    unittest.main()
