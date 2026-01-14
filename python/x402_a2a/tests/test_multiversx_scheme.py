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
# Imports might fail if dependencies aren't installed in the environment, 
# so we mock the imports for the test file to be valid python syntax 
# even if sdk is missing in this env (though functionality test requires them).
# For now, we assume we can import the local module.

# We need to make sure x402_a2a.schemes.multiversx can be imported.
# If dependencies are missing, the import inside multiversx.py will fail.
# So we might need to mock sys.modules for multiversx_sdk_core/wallet before importing.

import sys
from unittest.mock import MagicMock

# Mock libs before importing the scheme to avoid ImportError
sys.modules["multiversx_sdk_core"] = MagicMock()
sys.modules["multiversx_sdk_core"] = MagicMock()
sys.modules["multiversx_sdk_core.serializer"] = MagicMock()
sys.modules["multiversx_sdk_wallet"] = MagicMock()
sys.modules["pydantic"] = MagicMock() # Mock pydantic

# Mock x402 types since x402 package is not installable on Py3.9
x402_mock = MagicMock()
types_mock = MagicMock()

class MockPaymentRequirements:
    def __init__(self, scheme, network, asset, pay_to, max_amount_required, resource, description, max_timeout_seconds, mime_type, extra):
        self.scheme = scheme
        self.network = network
        self.asset = asset
        self.pay_to = pay_to
        self.max_amount_required = max_amount_required
        self.resource = resource
        self.description = description
        self.max_timeout_seconds = max_timeout_seconds
        self.mime_type = mime_type
        self.extra = extra

class MockPaymentPayload:
    def __init__(self, x402_version, scheme, network, payload):
        self.x402_version = x402_version
        self.scheme = scheme
        self.network = network
        self.payload = payload

# Define dummy classes for types used in type hints
class Mockx402ExtensionConfig: pass
class Mockx402ServerConfig: pass
class MockContext: pass
class MockEvent: pass

# Assign these classes to the modules where they are expected
# We need to construct the module hierarchy carefully

# Mock config types
config_mock = MagicMock()
config_mock.x402ExtensionConfig = Mockx402ExtensionConfig
config_mock.x402ServerConfig = Mockx402ServerConfig
# Constants
config_mock.X402_EXTENSION_URI = "http://example.com"
sys.modules["x402_a2a.types.config"] = config_mock

# Mock types package
types_pkg_mock = MagicMock()
types_pkg_mock.x402ExtensionConfig = Mockx402ExtensionConfig
types_pkg_mock.x402ServerConfig = Mockx402ServerConfig
# Re-apply strict types
types_pkg_mock.PaymentRequirements = MockPaymentRequirements
types_pkg_mock.PaymentPayload = MockPaymentPayload

x402_mock.types = types_pkg_mock
# Make x402 look like a package
x402_mock.__path__ = []

sys.modules["x402"] = x402_mock
sys.modules["x402.types"] = types_pkg_mock
sys.modules["x402.facilitator"] = MagicMock()
sys.modules["x402.chains"] = MagicMock()
sys.modules["x402.common"] = MagicMock()
sys.modules["x402.clients"] = MagicMock()
sys.modules["x402.clients.base"] = MagicMock()

# Mock other a2a dependencies
sys.modules["eth_account"] = MagicMock()
sys.modules["eth_account.messages"] = MagicMock()
sys.modules["eth_account.signers"] = MagicMock()
sys.modules["eth_account.signers.local"] = MagicMock()
sys.modules["web3"] = MagicMock()
sys.modules["httpx"] = MagicMock()

# Also mock a2a sdk as it is imported in __init__
a2a_mock = MagicMock()
a2a_mock.__path__ = []
sys.modules["a2a"] = a2a_mock

server_mock = MagicMock()
server_mock.__path__ = []
sys.modules["a2a.server"] = server_mock

# Mock submodules
sys.modules["a2a.types"] = MagicMock()
sys.modules["a2a.server.agent_execution"] = MagicMock()
sys.modules["a2a.server.agent_execution.agent_executor"] = MagicMock()
sys.modules["a2a.server.agent_execution.context"] = MagicMock()
sys.modules["a2a.server.events"] = MagicMock()
sys.modules["a2a.server.events.event_queue"] = MagicMock()
sys.modules["a2a.server.tasks"] = MagicMock() # Added missing mock

# Assign to parent for attribute access
a2a_mock.server = server_mock

# Now import the scheme
from x402_a2a.schemes.multiversx import MultiversXScheme

class TestMultiversXScheme(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D") # Devnet

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
        # USDC-123 hex: 555344432d313233
        # 100 hex: 64
        self.assertIn("ESDTTransfer@", req.extra["data_payload"])
        self.assertIn("555344432d313233", req.extra["data_payload"])
        self.assertIn("64", req.extra["data_payload"])

    @patch("x402_a2a.schemes.multiversx.Transaction")
    @patch("x402_a2a.schemes.multiversx.Address")
    def test_construct_payment_payload(self, mock_addr, mock_tx):
        # Mock setup
        mock_signer = MagicMock()
        mock_signer.sign.return_value = bytes.fromhex("aabbcc")
        
        mock_tx_instance = MagicMock()
        mock_tx_instance.serialize_for_signing.return_value = b"bytes"
        # Return dict with bytes signature to test hex conversion
        mock_tx_instance.to_dictionary.return_value = {
            "nonce": 1, 
            "signature": bytes.fromhex("aabbcc"),
            "data": b"mockdata"
        }
        mock_tx.return_value = mock_tx_instance

        # Call
        req = self.scheme.create_payment_requirements(100, "USDC-123", "erd1rec")
        # Sender address and nonce
        payload = self.scheme.construct_payment_payload(req, mock_signer, "erd1send", 1)

        # Assert
        self.assertEqual(payload.payload["signature"], "aabbcc") # Should be hex string
        mock_tx.assert_called()
        # Verify receiver set correctly
        mock_addr.new_from_bech32.assert_any_call("erd1rec")

    def test_resolve_did(self):
        # Valid DID
        did = "did:pkh:mvx:1:erd1alice"
        addr = self.scheme.resolve_did_to_address(did)
        self.assertEqual(addr, "erd1alice")

        # Invalid DID
        with self.assertRaises(ValueError):
            self.scheme.resolve_did_to_address("did:key:z123")
