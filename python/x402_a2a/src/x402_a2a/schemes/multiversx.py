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

import base64
import time
from typing import Any, Dict, Optional, Union, Protocol

from x402.types import PaymentPayload, PaymentRequirements

# User /mvx-python-specialist patterns (SDK v2)
from multiversx_sdk import (
    Address,
    TransactionsFactoryConfig,
    TransferTransactionsFactory,
    Token,
    TokenTransfer
)

from .multiversx_config import MultiversXConfig

class ISigner(Protocol):
    """Protocol for MultiversX transaction signers."""
    def sign_transaction(self, tx: Any) -> bytes: ...

class MultiversXScheme:
    """
    Implements the x402 payment scheme for MultiversX (mvx) with Relayed V3 support.
    Aligned with the 'Exact' scheme implementation logic.
    """
    SCHEME_NAME: str = "mvx"

    def __init__(self, chain_id: str = "1", config: Optional[MultiversXConfig] = None):
        """
        Initializes the MultiversX scheme.
        
        Args:
            chain_id: The MultiversX chain ID (e.g., "1" for Mainnet, "D" for Devnet).
            config: Optional specialized configuration for protocol constants.
        """
        self.chain_id = chain_id
        self.config = config or MultiversXConfig()
        factory_config = TransactionsFactoryConfig(chain_id=chain_id)
        self.factory = TransferTransactionsFactory(config=factory_config)

    def create_payment_requirements(
        self,
        amount: int,
        token_identifier: str,
        receiver: str,
        resource: str = "",
        description: str = "",
        max_timeout_seconds: Optional[int] = None
    ) -> PaymentRequirements:
        """
        [Functional Core] Generates the PaymentRequirements for MultiversX.
        
        Args:
            amount: Amount in atomic units.
            token_identifier: Token ID (e.g., "EGLD", or "USDC-c76f1f").
            receiver: Bech32 address of the recipient.
            resource: The resource being paid for.
            description: Human-readable description.
            max_timeout_seconds: Payment validity timeout.
        """
        # Validate inputs per specs 4.2
        self.validate_payment_requirements(amount, token_identifier, receiver)

        timeout = max_timeout_seconds or self.config.DEFAULT_TIMEOUT_SECONDS
        
        # Enhance requirements per specs 4.2 (gas, method logic)
        updated_reqs = self.enhance_payment_requirements(
            token_identifier, amount, receiver
        )
        data_payload = updated_reqs["data_payload"]
        gas_limit = updated_reqs["gasLimit"]
        transfer_method = updated_reqs["assetTransferMethod"]

        return PaymentRequirements(
            scheme=self.SCHEME_NAME,
            network=f"mvx:{self.chain_id}",
            asset=token_identifier,
            pay_to=receiver,
            max_amount_required=str(amount),
            resource=resource,
            description=description,
            max_timeout_seconds=timeout,
            mime_type="application/json",
            extra={
                "data_payload": data_payload,
                "chain_id": self.chain_id,
                "assetTransferMethod": transfer_method,
                "gasLimit": gas_limit
            }
        )

    def construct_payment_payload(
        self,
        requirements: PaymentRequirements,
        signer: ISigner,
        sender_address: str,
        nonce: int
    ) -> PaymentPayload:
        """
        [Functional Core/Shell] Constructs and signs the transaction.
        
        Args:
            requirements: The original payment requirements.
            signer: An object implementing ISigner (e.g., multiversx_sdk.Account).
            sender_address: Bech32 address of the payer.
            nonce: Transaction nonce for the sender.
        """
        now = int(time.time())
        data_payload = requirements.extra.get("data_payload", "")
        
        transfer_method = requirements.extra.get("assetTransferMethod")
        relayer = requirements.extra.get("relayer")
        
        # Version 1 for direct value transfer, Version 2 for Relayed V3
        version = 1 if transfer_method == self.config.TRANSFER_METHOD_DIRECT else 2
        
        is_egld = requirements.asset == "EGLD"
        sender_addr_obj = Address.new_from_bech32(sender_address)
        
        if is_egld:
            tx = self.factory.create_transaction_for_native_token_transfer(
                sender=sender_addr_obj,
                receiver=Address.new_from_bech32(requirements.pay_to),
                native_amount=int(requirements.max_amount_required)
            )
            # Only setting data for EGLD if present (e.g. comments)
            if data_payload:
                tx.data = data_payload.encode()
        else:
            # ESDT Transfer using SDK Factory - Strict V2 Compliance
            tx = self.factory.create_transaction_for_esdt_transfer(
                sender=sender_addr_obj,
                receiver=Address.new_from_bech32(requirements.pay_to),
                token_transfers=[
                    TokenTransfer(
                        token=Token(requirements.asset),
                        amount=int(requirements.max_amount_required)
                    )
                ]
            )
            # Factory sets the correct data for ESDT, do not overwrite with data_payload
        
        tx.nonce = nonce
        # tx.data is already set by factory or above block
        tx.gas_limit = requirements.extra.get("gasLimit", self.config.GAS_BASE_COST)
        tx.version = version
        
        if relayer:
            tx.relayer = Address.new_from_bech32(relayer)

        # Signing (Manual signing using SDK v2 patterns)
        tx.signature = signer.sign_transaction(tx)

        payload_dict = {
            "nonce": tx.nonce,
            "value": str(tx.value),
            "receiver": tx.receiver.bech32(),
            "sender": tx.sender.bech32(),
            "gasPrice": tx.gas_price or self.config.GAS_PRICE_DEFAULT,
            "gasLimit": tx.gas_limit,
            "data": data_payload,
            "chainID": tx.chain_id,
            "version": tx.version,
            "signature": tx.signature.hex(),
            "validAfter": now - 600, # Standard buffer
            "validBefore": now + (requirements.max_timeout_seconds or self.config.DEFAULT_TIMEOUT_SECONDS)
        }
        
        if relayer:
            payload_dict["relayer"] = relayer

        return PaymentPayload(
            x402_version=1,
            scheme=self.SCHEME_NAME,
            network=f"mvx:{self.chain_id}",
            payload=payload_dict
        )

    def verify_transaction_content(self, tx_data: Dict[str, Any], request: PaymentRequirements) -> bool:
        """
        [GREEN] Verifies that a fetched transaction matches the payment request.
        
        Args:
            tx_data: Dictionary representing the transaction data from a network provider.
            request: The original payment requirements to verify against.
        """
        # 1. Verify Receiver
        is_egld = request.asset == "EGLD"
        if is_egld:
            if tx_data.get("receiver") != request.pay_to:
                return False
        else:
            # For MultiESDT, tx.receiver is usually the sender or the pay_to 
            # depending on whether it's relayed or direct.
            actual_receiver = tx_data.get("receiver")
            actual_sender = tx_data.get("sender")
            if actual_receiver != actual_sender and actual_receiver != request.pay_to:
                 return False

        # 2. Verify Data Field
        expected_data = request.extra.get("data_payload", "")
        actual_data_raw = tx_data.get("data", "")
        
        actual_data = self._decode_transaction_data(actual_data_raw)
        if actual_data != expected_data:
            return False
            
        # 3. Verify Status
        if tx_data.get("status") != "success":
            return False
            
        return True

    def calculate_gas_limit(self, data_string: str, token_identifier: str) -> int:
        """
        Calculates gas limit based on the specialized 'Exact' formula.
        """
        data_len = len(data_string.encode())
        gas_limit = (
            self.config.GAS_BASE_COST +
            (self.config.GAS_PER_BYTE * data_len) +
            self.config.GAS_MULTI_TRANSFER_COST + 
            self.config.GAS_RELAYED_COST
        )
        
        # Buffer for Smart Contract execution (ESDT or SC calls)
        if token_identifier != "EGLD" or data_string:
            gas_limit += 10000000
            
        return gas_limit

    def resolve_did_to_address(self, did: str) -> str:
        """
        Resolves a did:pkh:mvx:{chain_id}:{address} to a bech32 address.
        """
        parts = did.split(":")
        if len(parts) >= 5 and parts[1] == "pkh" and parts[2] == "mvx":
             return parts[4]
        raise ValueError(f"Invalid MultiversX DID: {did}")

    def _construct_transfer_data_string(self, token: str, amount: int, receiver: str) -> str:
        """Helper to construct MultiESDTNFTTransfer data string."""
        if token == "EGLD":
            return ""
            
        dest_hex = Address.new_from_bech32(receiver).hex()
        token_hex = token.encode().hex()
        amount_hex = hex(amount)[2:]
        if len(amount_hex) % 2 != 0:
            amount_hex = "0" + amount_hex
            
        return f"MultiESDTNFTTransfer@{dest_hex}@01@{token_hex}@00@{amount_hex}"

    def _decode_transaction_data(self, data: Union[str, bytes]) -> str:
        """Safely decodes transaction data (handles base64 or plain string)."""
        if not data:
            return ""
        if isinstance(data, bytes):
            data = data.decode()
        
        # Heuristic: if it looks like MultiESDT, it's not encoded
        if data.startswith("MultiESDT") or data.startswith("ESDT"):
            return data
            
        try:
            return base64.b64decode(data).decode()
        except Exception:
            return data

    def parse_price(self, amount_str: str, decimals: int = 18) -> int:
        """
        [Spec 4.2] Converts input amounts to atomic units.
        Uses Decimal for precision to avoid floating point errors.
        """
        from decimal import Decimal
        try:
            if "." in amount_str:
                d = Decimal(amount_str)
                return int(d * (10 ** decimals))
            return int(amount_str)
        except Exception:
            raise ValueError(f"Invalid price format: {amount_str}")

    def enhance_payment_requirements(self, token: str, amount: int, receiver: str) -> Dict[str, Any]:
        """
        [Spec 4.2] Injects default gas_limit and transfer method.
        """
        is_egld = token == "EGLD"
        transfer_method = (
            self.config.TRANSFER_METHOD_DIRECT if is_egld 
            else self.config.TRANSFER_METHOD_ESDT
        )
        
        data_payload = self._construct_transfer_data_string(
            token, amount, receiver
        )
        
        gas_limit = self.calculate_gas_limit(data_payload, token)
        
        return {
            "gasLimit": gas_limit,
            "assetTransferMethod": transfer_method,
            "data_payload": data_payload
        }

    def validate_payment_requirements(self, amount: int, token: str, receiver: str):
        """
        [Spec 4.2] Enforces strictly valid addresses and tokens.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
            
        # Basic Bech32 validation (starts with erd1, length check)
        if not receiver.startswith("erd1") or len(receiver) != 62:
             raise ValueError(f"Invalid receiver address format: {receiver}")
             
        # Token ID validation
        if token != "EGLD" and "-" not in token:
             # Basic check, regex would be stricter per spec ^[A-Z0-9]{3,8}-[0-9a-fA-F]{6}$
             raise ValueError(f"Invalid token identifier format: {token}")
