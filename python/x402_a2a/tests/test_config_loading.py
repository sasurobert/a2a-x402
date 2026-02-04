import unittest
import os
import sys
import importlib.util
from unittest.mock import patch

# Load module directly from file path to avoid package import issues
file_path = os.path.join(os.path.dirname(__file__), "../src/x402_a2a/schemes/multiversx_config.py")
spec = importlib.util.spec_from_file_location("multiversx_config", file_path)
module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(module)
except Exception as e:
    # If this fails, it might be because of relative imports inside the file? 
    # But multiversx_config.py has no relative imports.
    print(f"Failed to load module: {e}")

MultiversXConfig = module.MultiversXConfig

class TestConfig(unittest.TestCase):
    def test_load_from_env(self):
        with patch.dict(os.environ, {"MVX_GAS_BASE_COST": "99999"}):
             try:
                 config = MultiversXConfig.from_env()
                 self.assertEqual(config.GAS_BASE_COST, 99999)
             except AttributeError:
                 self.fail("MultiversXConfig.from_env() not implemented")
