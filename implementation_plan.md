# Production Readiness Implementation Plan: MultiversX Integration

**Goal:** Refactor the `x402_a2a` MultiversX integration to be production-ready by externalizing configuration, implementing a concrete server executor, and adding real (non-mocked) integration tests.

**Architecture:**
1.  **Configuration**: Use `pydantic-settings` or standard `os.environ` to load config, removing hardcoded defaults from code.
2.  **Server Executor**: Implement `MultiversXServerExecutor` inheriting from `x402ServerExecutor` to handle `verify` and `settle` logic using the transparent `MultiversXScheme`.
3.  **Testing**: Create a strictly separated `tests/integration/` suite that requires a real private key and interacts with **Devnet**.

**Tech Stack:** Python 3.10+, `multiversx-sdk`, `unittest` (standard lib).

---

## Task 1: Refactor Configuration (Remove Hardcoding)

**Files:**
- Modify: `python/x402_a2a/src/x402_a2a/schemes/multiversx_config.py`

**Step 1: Write the failing test**
Create `tests/test_config_loading.py`:
```python
import unittest
import os
from x402_a2a.schemes.multiversx_config import MultiversXConfig

class TestConfig(unittest.TestCase):
    def test_load_from_env(self):
        os.environ["MVX_GAS_BASE_COST"] = "99999"
        config = MultiversXConfig.from_env()
        self.assertEqual(config.GAS_BASE_COST, 99999)
        del os.environ["MVX_GAS_BASE_COST"]
```

**Step 2: Verification**
Run `python3 -m unittest tests/test_config_loading.py`. Expected: Fail/AttributeError.

**Step 3: Implementation**
Modify `python/x402_a2a/src/x402_a2a/schemes/multiversx_config.py`:
```python
import os
from dataclasses import dataclass

@dataclass
class MultiversXConfig:
    """ ... existing docstring ... """
    GAS_BASE_COST: int = 50000
    # ... other fields ...

    @classmethod
    def from_env(cls) -> "MultiversXConfig":
        return cls(
            GAS_BASE_COST=int(os.getenv("MVX_GAS_BASE_COST", 50000)),
            # ... map other fields ...
        )
```

**Step 4: Verification**
Run test again. Expected: PASS.

---

## Task 2: Implement Concrete Server Executor

**Files:**
- Create: `python/x402_a2a/src/x402_a2a/executors/multiversx_executor.py`
- Modify: `python/x402_a2a/src/x402_a2a/__init__.py` (export it)

**Step 1: Write the failing test**
Create `tests/test_executor_instantiation.py`:
```python
import unittest
from x402_a2a.executors.multiversx_executor import MultiversXServerExecutor

class TestMvxExecutor(unittest.TestCase):
    def test_instantiation(self):
        # Mocks for deps
        delegate = unittest.mock.MagicMock()
        config = unittest.mock.MagicMock()
        executor = MultiversXServerExecutor(delegate, config, chain_id="D")
        self.assertIsNotNone(executor)
```

**Step 2: Verification**
Run test. Expected: Fail (ImportError).

**Step 3: Implementation**
Create `python/x402_a2a/src/x402_a2a/executors/multiversx_executor.py`:
```python
from typing import override
from x402_a2a.executors import x402ServerExecutor
from x402_a2a.schemes.multiversx import MultiversXScheme
from x402_a2a.types import PaymentPayload, PaymentRequirements, VerifyResponse, SettleResponse

class MultiversXServerExecutor(x402ServerExecutor):
    def __init__(self, delegate, config, chain_id: str = "1"):
        super().__init__(delegate, config)
        self.scheme = MultiversXScheme(chain_id=chain_id)
        # Note: In a real implementation, we need a network provider to check tx status.
        # For 'verify_payment', we check the payload structure.
        # For 'settle_payment', we might need to query the chain.

    @override
    async def verify_payment(self, payload: PaymentPayload, requirements: PaymentRequirements) -> VerifyResponse:
        # 1. Structural check
        if payload.scheme != "mvx":
             return VerifyResponse(is_valid=False, invalid_reason="Invalid scheme")
        
        # 2. Logic check (signature verification, data field match)
        # This requires the scheme to have a stateless check method or network call.
        # For now, we use the scheme's 'verify_transaction_content' which assumes we have fetched tx data.
        # BUT payload.payload contains the signed tx info.
        
        # TODO: Implement signature verification here using UserVerifier or SDK
        return VerifyResponse(is_valid=True)

    @override
    async def settle_payment(self, payload: PaymentPayload, requirements: PaymentRequirements) -> SettleResponse:
        # 1. Broadcast the transaction (if not already on chain)
        # or 2. Just return success if we are trusting the client to broadcast (common in simple payments)
        return SettleResponse(success=True, network=f"mvx:{self.scheme.chain_id}")
```
*Note: This implementation needs to use `ApiNetworkProvider` to be useful. We will add that in Task 3.*

---

## Task 3: Real Integration Test (Devnet)

**Files:**
- Create: `python/x402_a2a/tests/integration/test_multiversx_real.py`

**Step 1: Write the test**
```python
import unittest
import os
import time
from multiversx_sdk import Account, Mnemonic
from x402_a2a.schemes.multiversx import MultiversXScheme

class TestRealDevnet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mnemonic = os.getenv("MVX_TEST_MNEMONIC")
        if not cls.mnemonic:
            raise unittest.SkipTest("MVX_TEST_MNEMONIC not set")
            
    def test_flow(self):
        # 1. Setup scheme
        scheme = MultiversXScheme(chain_id="D") # Devnet
        
        # 2. Create requirements
        # ...
        
        # 3. Sign and Broadcast
        # Use ApiNetworkProvider to broadcast
        # ...
        
        # 4. Verify
        # ...
```

**Step 2: Verification**
Run with proper env vars. Expected: Pass if funded, Fail if no funds/network content.

---

## Task 4: Fix Dependencies & Clean up

**Step 1: Fix `pyproject.toml`**
Ensure `multiversx-sdk` is pegged to a stable version and development deps include `pytest`, `pytest-asyncio`.

**Step 2: Clean up Tests**
Remove `tests/test_integration_real.py` (the fake one).

---
