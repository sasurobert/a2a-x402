
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# 1. Setup Environment & Mocks BEFORE importing the module under test
# This ensures we don't hit ModuleNotFoundError for optional dependencies like 'a2a'
sys.modules["x402"] = MagicMock()
sys.modules["x402.types"] = MagicMock()
sys.modules["x402.facilitator"] = MagicMock() # Added missing mock
sys.modules["x402.common"] = MagicMock() # Added missing mock
sys.modules["x402.clients"] = MagicMock() # Added missing mock
sys.modules["x402.clients.base"] = MagicMock() # Added missing mock
sys.modules["a2a"] = MagicMock()
sys.modules["a2a.types"] = MagicMock() # Added missing mock
sys.modules["a2a.server"] = MagicMock()
sys.modules["a2a.server.agent_execution"] = MagicMock()
sys.modules["a2a.server.agent_execution.agent_executor"] = MagicMock()
sys.modules["a2a.server.agent_execution.context"] = MagicMock() # Added missing mock
sys.modules["a2a.server.events"] = MagicMock() 
sys.modules["a2a.server.events.event_queue"] = MagicMock() # Added missing mock
sys.modules["multiversx_sdk"] = MagicMock()
sys.modules["pydantic"] = MagicMock() # Added pydantic mock
sys.modules["eth_account"] = MagicMock() # Added eth_account mock
import importlib.util

# Now we can safely import our module
# We need to make sure the src path is in python path
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Mock the package structure to prevent real loading
sys.modules["x402_a2a"] = MagicMock()
sys.modules["x402_a2a.schemes"] = MagicMock()

# Load Config manually
config_path = os.path.join(src_path, "x402_a2a/schemes/multiversx_config.py")
spec_conf = importlib.util.spec_from_file_location("x402_a2a.schemes.multiversx_config", config_path)
module_conf = importlib.util.module_from_spec(spec_conf)
sys.modules["x402_a2a.schemes.multiversx_config"] = module_conf
spec_conf.loader.exec_module(module_conf)

# Load target module
file_path = os.path.join(src_path, "x402_a2a/schemes/multiversx.py")
spec = importlib.util.spec_from_file_location("x402_a2a.schemes.multiversx", file_path)
module = importlib.util.module_from_spec(spec)
sys.modules["x402_a2a.schemes.multiversx"] = module
spec.loader.exec_module(module)

MultiversXScheme = module.MultiversXScheme
# DUMMY PaymentRequirements because x402.types is mocked
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class DummyRequirements:
    scheme: str
    network: str
    asset: str
    pay_to: str # ensure attribute matches usage (pay_to)
    max_amount_required: str
    resource: str = ""
    description: str = ""
    max_timeout_seconds: int = 3600
    mime_type: str = "application/json"
    extra: Dict[str, Any] = field(default_factory=dict)

class TestMultiversXSchemeSDK(unittest.TestCase):
    def setUp(self):
        self.scheme = MultiversXScheme(chain_id="D")
        # We need to spy on the factory to ensure methods are called
        self.scheme.factory = MagicMock() 

    def test_construct_payment_payload_esdt_uses_factory(self):
        """
        [TDD] Verifies that construct_payment_payload calls 
        create_transaction_for_esdt_transfer when token is NOT EGLD.
        """
        # Arrange
        req = DummyRequirements(
            scheme="mvx",
            network="mvx:D",
            asset="USDC-123456",
            pay_to="erd1receiver",
            max_amount_required="1000",
            extra={
                "assetTransferMethod": "esdt",
                "data_payload": "OLD_MANUAL_STRING" 
            }
        )
        signer = MagicMock()
        signer.sign_transaction.return_value = bytes.fromhex("aabbcc")
        
        # Act
        self.scheme.construct_payment_payload(
            requirements=req,
            signer=signer,
            sender_address="erd1sender",
            nonce=10
        )
        
        # Assert
        self.scheme.factory.create_transaction_for_esdt_transfer.assert_called_once()
        
    def test_construct_payment_payload_egld_uses_factory(self):
        """
        Verifies EGLD transfers use create_transaction_for_native_token_transfer.
        """
        req = DummyRequirements(
            scheme="mvx",
            network="mvx:D",
            asset="EGLD",
            pay_to="erd1receiver",
            max_amount_required="1000000000000000000",
            extra={"assetTransferMethod": "direct"}
        )
        signer = MagicMock()
        signer.sign_transaction.return_value = bytes.fromhex("aabbcc")
        
        self.scheme.construct_payment_payload(
            requirements=req,
            signer=signer,
            sender_address="erd1sender",
            nonce=15
        )
        
        self.scheme.factory.create_transaction_for_native_token_transfer.assert_called_once()

    def test_create_payment_requirements_validation(self):
        """
        [TDD] Verifies input validation logic in create_payment_requirements.
        """
        # Negative Amount
        with self.assertRaises(ValueError):
            self.scheme.create_payment_requirements(
                amount=-100,
                token_identifier="EGLD",
                receiver="erd1receiver"
            )

        # Invalid Receiver
        with self.assertRaises(ValueError):
            self.scheme.create_payment_requirements(
                amount=100,
                token_identifier="EGLD",
                receiver="invalid_bech32"
            )

        # Invalid Token ID
        with self.assertRaises(ValueError):
            self.scheme.create_payment_requirements(
                amount=100,
                token_identifier="INVALIDTOKEN", # Missing hyphen/ID
                receiver="erd1receiver" + "a"*50 # Valid length rough check
            )

    def test_create_payment_requirements_success(self):
        """
        [TDD] Verifies happy path for create_payment_requirements by checking constructor calls.
        """
        # Create a spy for PaymentRequirements (it's already a Mock in the module)
        # We need to access the imported name in the module_under_test
        # self.scheme is an instance. The module is available via self.scheme.__class__.__module__? 
        # No, we loaded it in the test setup. 
        # But we need access to the PaymentRequirements mock used inside construct_payment_payload.
        # Since we mocked x402.types.PaymentRequirements, the module has that reference.
        
        # We can access it via the module object we loaded manually in setUp or just global?
        # In this file, we did `MultiversXScheme = module.MultiversXScheme`. 
        # But `module` variable is global in this file (at top level).
        # We need to access `module.PaymentRequirements`.
        # Wait, `module` variable names "module" is defined at top level.
        
        # Reset the mock to be sure
        module.PaymentRequirements.reset_mock()
        
        req = self.scheme.create_payment_requirements(
            amount=1000,
            token_identifier="USDC-123456",
            receiver="erd1receiver" + "a"*50,
            description="Test Payment"
        )
        
        # Verify PaymentRequirements was initialized with expected args
        # We check that 'gasLimit' is in the 'extra' dict passed to constructor
        args, kwargs = module.PaymentRequirements.call_args
        self.assertIn("extra", kwargs)
        self.assertIn("gasLimit", kwargs["extra"])
        self.assertEqual(kwargs["asset"], "USDC-123456")
        
        # Verify logic applied
        self.assertIn("data_payload", kwargs["extra"])
        # Should contain transfer string
        self.assertIn("MultiESDTNFTTransfer", kwargs["extra"]["data_payload"])

if __name__ == "__main__":
    unittest.main()
