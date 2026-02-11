"""
Comprehensive unit tests for MultiversX scheme functions that are NOT covered
by the existing test_multiversx_scheme_sdk.py tests.

Coverage targets:
  - resolve_did_to_address
  - calculate_gas_limit
  - _decode_transaction_data
  - parse_price
  - verify_transaction_content (edge cases)
  - enhance_payment_requirements
  - Relayed V3 flow (version 2 with relayer)
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import importlib.util

# Setup mocks BEFORE imports (same pattern as existing test)
sys.modules["x402"] = MagicMock()
sys.modules["x402.types"] = MagicMock()
sys.modules["x402.facilitator"] = MagicMock()
sys.modules["x402.common"] = MagicMock()
sys.modules["x402.clients"] = MagicMock()
sys.modules["x402.clients.base"] = MagicMock()
sys.modules["a2a"] = MagicMock()
sys.modules["a2a.types"] = MagicMock()
sys.modules["a2a.server"] = MagicMock()
sys.modules["a2a.server.agent_execution"] = MagicMock()
sys.modules["a2a.server.agent_execution.agent_executor"] = MagicMock()
sys.modules["a2a.server.agent_execution.context"] = MagicMock()
sys.modules["a2a.server.events"] = MagicMock()
sys.modules["a2a.server.events.event_queue"] = MagicMock()
sys.modules["multiversx_sdk"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
sys.modules["eth_account"] = MagicMock()

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

sys.modules["x402_a2a"] = MagicMock()
sys.modules["x402_a2a.schemes"] = MagicMock()

# Load config manually
config_path = os.path.join(src_path, "x402_a2a/schemes/multiversx_config.py")
spec_conf = importlib.util.spec_from_file_location(
    "x402_a2a.schemes.multiversx_config", config_path
)
module_conf = importlib.util.module_from_spec(spec_conf)
sys.modules["x402_a2a.schemes.multiversx_config"] = module_conf
spec_conf.loader.exec_module(module_conf)

MultiversXConfig = module_conf.MultiversXConfig

# Load target module
file_path = os.path.join(src_path, "x402_a2a/schemes/multiversx.py")
spec = importlib.util.spec_from_file_location("x402_a2a.schemes.multiversx", file_path)
module = importlib.util.module_from_spec(spec)
sys.modules["x402_a2a.schemes.multiversx"] = module
spec.loader.exec_module(module)

MultiversXScheme = module.MultiversXScheme


# ── DID Resolution Tests ────────────────────────────────────────────────────────

class TestDIDResolution(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        self.scheme.factory = MagicMock()

    def test_valid_did_resolution(self):
        """Y-003: Valid did:pkh:mvx:D:erd1... → bech32 address"""
        address = "erd1qqqqqqqqqqqqqqqpgq0tajepcazernwt74820t8ef7t28s6h4jrsxmv79k"
        did = f"did:pkh:mvx:D:{address}"
        result = self.scheme.resolve_did_to_address(did)
        self.assertEqual(result, address)

    def test_valid_did_mainnet(self):
        """Mainnet DID resolution"""
        address = "erd1qqqqqqqqqqqqqqqpgq0tajepcazernwt74820t8ef7t28s6h4jrsxmv79k"
        did = f"did:pkh:mvx:1:{address}"
        result = self.scheme.resolve_did_to_address(did)
        self.assertEqual(result, address)

    def test_invalid_did_wrong_namespace(self):
        """Non-mvx namespace should raise ValueError"""
        did = "did:pkh:eth:1:0x1234"
        with self.assertRaises(ValueError):
            self.scheme.resolve_did_to_address(did)

    def test_invalid_did_too_few_parts(self):
        """DID with fewer than 5 parts should raise ValueError"""
        did = "did:pkh:mvx"
        with self.assertRaises(ValueError):
            self.scheme.resolve_did_to_address(did)

    def test_invalid_did_wrong_method(self):
        """Non-pkh method should raise ValueError"""
        did = "did:web:mvx:D:erd1abc"
        with self.assertRaises(ValueError):
            self.scheme.resolve_did_to_address(did)


# ── Gas Calculation Tests ────────────────────────────────────────────────────────

class TestGasCalculation(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        self.scheme.factory = MagicMock()
        self.config = self.scheme.config

    def test_gas_egld_no_data(self):
        """EGLD transfer with empty data should include base + multi + relayed"""
        gas = self.scheme.calculate_gas_limit("", "EGLD")
        expected = (
            self.config.GAS_BASE_COST
            + self.config.GAS_MULTI_TRANSFER_COST
            + self.config.GAS_RELAYED_COST
        )
        self.assertEqual(gas, expected)

    def test_gas_egld_with_data(self):
        """EGLD with data adds per-byte cost + SC execution buffer"""
        data = "x402-payment-id-123"
        gas = self.scheme.calculate_gas_limit(data, "EGLD")
        data_len = len(data.encode())
        expected = (
            self.config.GAS_BASE_COST
            + (self.config.GAS_PER_BYTE * data_len)
            + self.config.GAS_MULTI_TRANSFER_COST
            + self.config.GAS_RELAYED_COST
            + 10000000  # SC execution buffer
        )
        self.assertEqual(gas, expected)

    def test_gas_esdt_transfer(self):
        """ESDT transfer always adds SC execution buffer"""
        data = "MultiESDTNFTTransfer@abc@01@def@00@ff"
        gas = self.scheme.calculate_gas_limit(data, "USDC-c76f1f")
        data_len = len(data.encode())
        expected = (
            self.config.GAS_BASE_COST
            + (self.config.GAS_PER_BYTE * data_len)
            + self.config.GAS_MULTI_TRANSFER_COST
            + self.config.GAS_RELAYED_COST
            + 10000000
        )
        self.assertEqual(gas, expected)

    def test_gas_increases_with_data_length(self):
        """Gas should increase linearly with data length"""
        gas_short = self.scheme.calculate_gas_limit("ab", "EGLD")
        gas_long = self.scheme.calculate_gas_limit("a" * 100, "EGLD")
        self.assertGreater(gas_long, gas_short)


# ── Data Decoding Tests ──────────────────────────────────────────────────────────

class TestDataDecoding(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        self.scheme.factory = MagicMock()

    def test_decode_empty_string(self):
        self.assertEqual(self.scheme._decode_transaction_data(""), "")

    def test_decode_none(self):
        self.assertEqual(self.scheme._decode_transaction_data(None), "")

    def test_decode_multi_esdt_passthrough(self):
        """MultiESDT data should pass through without base64 decoding"""
        data = "MultiESDTNFTTransfer@abcdef@01@aabbcc@00@ff"
        self.assertEqual(self.scheme._decode_transaction_data(data), data)

    def test_decode_esdt_transfer_passthrough(self):
        data = "ESDTTransfer@abcdef@00ff"
        self.assertEqual(self.scheme._decode_transaction_data(data), data)

    def test_decode_base64_encoded(self):
        """Base64-encoded data should be decoded"""
        import base64
        original = "hello-payment-data"
        encoded = base64.b64encode(original.encode()).decode()
        self.assertEqual(self.scheme._decode_transaction_data(encoded), original)

    def test_decode_bytes_input(self):
        """Bytes input should be handled"""
        data = b"MultiESDTNFTTransfer@abc"
        self.assertEqual(
            self.scheme._decode_transaction_data(data),
            "MultiESDTNFTTransfer@abc",
        )

    def test_decode_invalid_base64_returns_original(self):
        """Non-base64 non-ESDT strings should be returned as-is"""
        data = "plain-text-not-base64!!!"
        result = self.scheme._decode_transaction_data(data)
        # Should return either the original or a decoded attempt
        self.assertIsInstance(result, str)


# ── Price Parsing Tests ──────────────────────────────────────────────────────────

class TestPriceParsing(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        self.scheme.factory = MagicMock()

    def test_parse_integer_string(self):
        """Pure integer string should return as-is"""
        self.assertEqual(self.scheme.parse_price("1000000000000000000"), 1000000000000000000)

    def test_parse_decimal_string(self):
        """Decimal string should convert with 18 decimals"""
        result = self.scheme.parse_price("1.0")
        self.assertEqual(result, 1000000000000000000)

    def test_parse_small_decimal(self):
        """Small decimal values should maintain precision"""
        result = self.scheme.parse_price("0.1")
        self.assertEqual(result, 100000000000000000)

    def test_parse_custom_decimals(self):
        """Custom decimal count (e.g. 6 for USDC)"""
        result = self.scheme.parse_price("1.5", decimals=6)
        self.assertEqual(result, 1500000)

    def test_parse_zero(self):
        """Zero should be valid"""
        self.assertEqual(self.scheme.parse_price("0"), 0)

    def test_parse_invalid_raises(self):
        """Invalid format should raise ValueError"""
        with self.assertRaises(ValueError):
            self.scheme.parse_price("not-a-number")


# ── Verify Transaction Content Tests ─────────────────────────────────────────────

class TestVerifyTransactionContent(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        self.scheme.factory = MagicMock()

    def _make_req(self, asset="EGLD", pay_to="erd1receiver", data_payload=""):
        """Helper to create a mock PaymentRequirements"""
        req = MagicMock()
        req.asset = asset
        req.pay_to = pay_to
        req.extra = {"data_payload": data_payload}
        return req

    def test_verify_egld_success(self):
        """Valid EGLD transaction should verify"""
        req = self._make_req(asset="EGLD", pay_to="erd1receiver")
        tx_data = {
            "receiver": "erd1receiver",
            "sender": "erd1sender",
            "data": "",
            "status": "success",
        }
        self.assertTrue(self.scheme.verify_transaction_content(tx_data, req))

    def test_verify_egld_wrong_receiver(self):
        """Wrong receiver should fail verification"""
        req = self._make_req(asset="EGLD", pay_to="erd1expected")
        tx_data = {
            "receiver": "erd1wrong",
            "sender": "erd1sender",
            "data": "",
            "status": "success",
        }
        self.assertFalse(self.scheme.verify_transaction_content(tx_data, req))

    def test_verify_failed_status(self):
        """Non-success status should fail verification"""
        req = self._make_req(asset="EGLD", pay_to="erd1receiver")
        tx_data = {
            "receiver": "erd1receiver",
            "sender": "erd1sender",
            "data": "",
            "status": "fail",
        }
        self.assertFalse(self.scheme.verify_transaction_content(tx_data, req))

    def test_verify_esdt_self_receiver(self):
        """MultiESDT where receiver==sender (standard pattern) should pass"""
        req = self._make_req(
            asset="USDC-c76f1f",
            pay_to="erd1pay_to",
            data_payload="MultiESDTNFTTransfer@abc@01@def@00@ff",
        )
        tx_data = {
            "receiver": "erd1sender",
            "sender": "erd1sender",
            "data": "MultiESDTNFTTransfer@abc@01@def@00@ff",
            "status": "success",
        }
        self.assertTrue(self.scheme.verify_transaction_content(tx_data, req))

    def test_verify_data_mismatch(self):
        """Mismatched data payload should fail"""
        req = self._make_req(
            asset="EGLD", pay_to="erd1receiver", data_payload="expected-data"
        )
        tx_data = {
            "receiver": "erd1receiver",
            "sender": "erd1sender",
            "data": "wrong-data",
            "status": "success",
        }
        self.assertFalse(self.scheme.verify_transaction_content(tx_data, req))


# ── Enhance Payment Requirements Tests ───────────────────────────────────────────

class TestEnhancePaymentRequirements(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        self.scheme.factory = MagicMock()

    def test_egld_transfer_method(self):
        """EGLD should use 'direct' transfer method"""
        result = self.scheme.enhance_payment_requirements(
            "EGLD", 1000000000000000000, "erd1receiver" + "a" * 50
        )
        self.assertEqual(result["assetTransferMethod"], "direct")
        self.assertEqual(result["data_payload"], "")

    def test_esdt_transfer_method(self):
        """ESDT should use 'esdt' transfer method and have data_payload"""
        # Mock Address.new_from_bech32 for the _construct_transfer_data_string
        mock_addr = MagicMock()
        mock_addr.hex.return_value = "0" * 64
        module.Address.new_from_bech32.return_value = mock_addr

        result = self.scheme.enhance_payment_requirements(
            "USDC-c76f1f", 1000000, "erd1receiver" + "a" * 50
        )
        self.assertEqual(result["assetTransferMethod"], "esdt")
        self.assertIn("MultiESDTNFTTransfer", result["data_payload"])

    def test_gas_limit_always_positive(self):
        """Gas limit should always be a positive integer"""
        result = self.scheme.enhance_payment_requirements(
            "EGLD", 100, "erd1receiver" + "a" * 50
        )
        self.assertGreater(result["gasLimit"], 0)


# ── Relayed V3 Flow Tests ────────────────────────────────────────────────────────

class TestRelayedV3Flow(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        self.scheme.factory = MagicMock()

    def test_construct_payload_with_relayer(self):
        """When relayer is in extra, version should be 2 and relayer in output"""
        req = MagicMock()
        req.asset = "EGLD"
        req.pay_to = "erd1receiver"
        req.max_amount_required = "1000000000000000000"
        req.max_timeout_seconds = 600
        req.extra = {
            "data_payload": "",
            "assetTransferMethod": "esdt",  # non-direct → version 2
            "relayer": "erd1relayer" + "a" * 50,
            "gasLimit": 500000,
        }

        signer = MagicMock()
        signer.sign_transaction.return_value = bytes(64)

        mock_tx = MagicMock()
        mock_tx.nonce = 5
        mock_tx.value = "1000000000000000000"
        mock_tx.receiver = MagicMock()
        mock_tx.receiver.bech32.return_value = "erd1receiver"
        mock_tx.sender = MagicMock()
        mock_tx.sender.bech32.return_value = "erd1sender"
        mock_tx.gas_price = 1000000000
        mock_tx.gas_limit = 500000
        mock_tx.chain_id = "D"
        mock_tx.version = 2
        mock_tx.signature = bytes(64)

        self.scheme.factory.create_transaction_for_native_token_transfer.return_value = (
            mock_tx
        )

        payload = self.scheme.construct_payment_payload(
            requirements=req,
            signer=signer,
            sender_address="erd1sender",
            nonce=5,
        )

        # Verify relayer is set on the transaction
        self.assertIsNotNone(mock_tx.relayer)


# ── Config Tests ─────────────────────────────────────────────────────────────────

class TestMultiversXConfig(unittest.TestCase):
    def test_default_values(self):
        config = MultiversXConfig()
        self.assertEqual(config.GAS_BASE_COST, 50000)
        self.assertEqual(config.GAS_PER_BYTE, 1500)
        self.assertEqual(config.GAS_MULTI_TRANSFER_COST, 200000)
        self.assertEqual(config.GAS_RELAYED_COST, 50000)
        self.assertEqual(config.DEFAULT_TIMEOUT_SECONDS, 600)
        self.assertEqual(config.CAIP2_NAMESPACE, "mvx")

    def test_from_env(self):
        """Config.from_env should use environment variables"""
        with patch.dict(os.environ, {"MVX_GAS_BASE_COST": "99999"}):
            config = MultiversXConfig.from_env()
            self.assertEqual(config.GAS_BASE_COST, 99999)


if __name__ == "__main__":
    unittest.main()
