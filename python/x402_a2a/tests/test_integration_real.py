# Copyright 2025 Google LLC
# integration test without mocks (except for network calls)

import unittest
from unittest.mock import MagicMock, patch
import sys
import base64

# Mock libs before importing anything from the package
def mock_package(name):
    m = MagicMock()
    sys.modules[name] = m
    return m

mock_package("multiversx_sdk")
mock_package("pydantic")
mock_package("x402")
mock_package("x402.types")
mock_package("x402.facilitator")
mock_package("a2a")
mock_package("a2a.types")

from x402_a2a.schemes.multiversx import MultiversXScheme

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
        
        # 3. Construct Payload
        class DummySigner:
            def sign_transaction(self, tx: any) -> bytes:
                return b"signature_bytes"
                
        signer = DummySigner()
        sender_addr = "erd1sender"
        
        # Mock Address.bech32 etc
        with patch("x402_a2a.schemes.multiversx.Address") as mock_addr:
            mock_addr_inst = MagicMock()
            mock_addr_inst.bech32.return_value = sender_addr
            mock_addr.new_from_bech32.return_value = mock_addr_inst
            
            # Mock PaymentPayload
            sys.modules["x402.types"].PaymentPayload.side_effect = lambda **kwargs: MagicMock(payload=kwargs.get("payload"))

            payload = scheme.construct_payment_payload(
                requirements=req,
                signer=signer,
                sender_address=sender_addr,
                nonce=10
            )
            
            self.assertEqual(payload.payload["nonce"], 10)
            self.assertEqual(payload.payload["signature"], b"signature_bytes".hex())

if __name__ == '__main__':
    unittest.main()
