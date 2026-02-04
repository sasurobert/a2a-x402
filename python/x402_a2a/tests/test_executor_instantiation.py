import unittest
from unittest.mock import MagicMock
import sys

# Mock dependencies
sys.modules["x402"] = MagicMock()
sys.modules["x402.types"] = MagicMock()
sys.modules["x402.facilitator"] = MagicMock()

sys.modules["a2a"] = MagicMock()
sys.modules["a2a.types"] = MagicMock()
sys.modules["a2a.server"] = MagicMock()
sys.modules["a2a.server.tasks"] = MagicMock()
sys.modules["a2a.server.agent_execution"] = MagicMock()
sys.modules["a2a.server.agent_execution.agent_executor"] = MagicMock()
sys.modules["a2a.server.agent_execution.context"] = MagicMock()

from x402_a2a.executors.multiversx_executor import MultiversXServerExecutor

class TestMvxExecutor(unittest.TestCase):
    def test_instantiation(self):
        delegate = MagicMock()
        config = MagicMock()
        try:
             executor = MultiversXServerExecutor(delegate, config, chain_id="D")
             self.assertIsNotNone(executor)
        except ImportError:
             self.fail("Could not import MultiversXServerExecutor")
