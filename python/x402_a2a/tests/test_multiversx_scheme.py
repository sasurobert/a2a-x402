# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest.mock import MagicMock, patch
import base64
import sys

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

# Now import the scheme
from x402_a2a.schemes.multiversx import MultiversXScheme
from x402_a2a.schemes.multiversx_config import MultiversXConfig

class TestMultiversXScheme(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")

    def test_create_payment_requirements(self):
        req = self.scheme.create_payment_requirements(
            amount=100,
            token_identifier="USDC-123",
            receiver="erd1rec",
            resource="/api/test",
            description="Test Payment"
        )
        self.assertEqual(req.scheme, "mvx")
        self.assertEqual(req.network, "mvx:D")
        self.assertIn("MultiESDTNFTTransfer@", req.extra["data_payload"])
        self.assertIn("555344432d313233", req.extra["data_payload"])
        self.assertIn("64", req.extra["data_payload"])

    @patch("x402_a2a.schemes.multiversx.TransferTransactionsFactory")
    @patch("x402_a2a.schemes.multiversx.Address")
    def test_construct_payment_payload(self, mock_addr, mock_factory):
        self.scheme = MultiversXScheme(chain_id="D")
        mock_signer = MagicMock()
        mock_signer.sign_transaction.return_value = bytes.fromhex("aabbcc")
        
        mock_tx = MagicMock()
        mock_tx.nonce = 1
        mock_tx.value = 0
        mock_tx.receiver.bech32.return_value = "erd1send"
        mock_tx.sender.bech32.return_value = "erd1send"
        mock_tx.gas_price = 1000000000
        mock_tx.gas_limit = 500000
        mock_tx.chain_id = "D"
        mock_tx.version = 2
        mock_tx.signature = bytes.fromhex("aabbcc")
        
        mock_factory_instance = mock_factory.return_value
        mock_factory_instance.create_transaction_for_native_token_transfer.return_value = mock_tx

        # Mock PaymentPayload since it's a MagicMock from sys.modules
        mock_payload_type = sys.modules["x402.types"].PaymentPayload
        mock_payload_type.side_effect = lambda **kwargs: MagicMock(**kwargs)

        req = self.scheme.create_payment_requirements(100, "USDC-123", "erd1rec")
        payload = self.scheme.construct_payment_payload(req, mock_signer, "erd1send", 1)

        mock_factory_instance.create_transaction_for_native_token_transfer.assert_called()

    def test_verify_transaction_content(self):
        req = self.scheme.create_payment_requirements(1000, "USDC-123", "erd1rec")
        valid_tx = {
            "receiver": "erd1sender",
            "sender": "erd1sender",
            "status": "success",
            "data": base64.b64encode(req.extra["data_payload"].encode()).decode()
        }
        self.assertTrue(self.scheme.verify_transaction_content(valid_tx, req))

if __name__ == "__main__":
    unittest.main()
