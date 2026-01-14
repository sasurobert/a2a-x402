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

from typing import Any, Dict, Optional, Union
import json
import base64
from x402.types import PaymentRequirements, PaymentPayload
from multiversx_sdk_core import Transaction, Address, TransactionComputer
from multiversx_sdk_wallet import UserSigner

class MultiversXScheme:
    """
    Implements the x402 payment scheme for MultiversX (mvx) with Relayed V3 support.
    """
    SCHEME_NAME = "mvx"

    def __init__(self, chain_id: str = "1"):
        self.chain_id = chain_id
        # Relayed V3 gas limit base is 50k + 50k + data. 
        # We set a safe default for the inner transaction.
        self.gas_limit_inner = 500000 
        self.tx_computer = TransactionComputer()

    def create_payment_requirements(
        self,
        amount: int,
        token_identifier: str,
        receiver: str,
        resource: str = "",
        description: str = ""
    ) -> PaymentRequirements:
        """
        [Functional Core] Generates the PaymentRequirements for MultiversX.
        The data field for ESDT transfer is pre-calculated here.
        """
        esdt_data = self._construct_esdt_data(token_identifier, amount)
        
        return PaymentRequirements(
            scheme=self.SCHEME_NAME,
            network=f"mvx:{self.chain_id}",
            asset=token_identifier,
            pay_to=receiver,
            max_amount_required=str(amount),
            resource=resource,
            description=description,
            max_timeout_seconds=600,
            mime_type="application/json",
            extra={
                "data_payload": esdt_data,
                "chain_id": self.chain_id
            }
        )

    def construct_payment_payload(
        self,
        requirements: PaymentRequirements,
        signer: UserSigner, # signer interface from simple-wallet
        sender_address: str,
        nonce: int
    ) -> PaymentPayload:
        """
        [Functional Core/Shell] Signs the Inner Transaction and returns PaymentPayload.
        Note: signer is passed in, matching a2a-x402 wallet.py pattern but using MX SDK.
        """
        # 1. Reconstruct data from requirements
        data_payload = requirements.extra.get("data_payload", "")
        if not data_payload:
            # Fallback if extra missing, reconstruct
            data_payload = self._construct_esdt_data(
                requirements.asset, 
                int(requirements.max_amount_required)
            )

        # 2. Construct Inner Transaction
        # Relayed Transaction V3 Inner Tx:
        # Value must be 0 for ESDT transfer (handled via data field)
        # Note: SDK 0.8.x Transaction expects strings for sender/receiver, and bytes for data
        tx = Transaction(
            nonce=nonce,
            value=0,
            sender=sender_address,
            receiver=requirements.pay_to,
            gas_limit=self.gas_limit_inner,
            data=data_payload.encode(),
            chain_id=self.chain_id,
            version=2 
        )

        # 3. Sign
        # Getbytes for signing using TransactionComputer
        tx_bytes = self.tx_computer.compute_bytes_for_signing(tx)
        signature = signer.sign(tx_bytes)
        tx.signature = signature

        # 4. Construct Payload Dictionary matching Relayed V3 expectation
        # The payload delivered to the Relayer (CP) needs to be the inner tx fields + signature.
        # Use TransactionComputer internal method to get dict
        payload_dict = self.tx_computer._to_dictionary(tx)
        
        # Ensure signature is hex string for the payload
        if isinstance(payload_dict.get("signature"), bytes):
            payload_dict["signature"] = payload_dict["signature"].hex()
        elif hasattr(tx.signature, "hex"):
             payload_dict["signature"] = tx.signature.hex()

        return PaymentPayload(
            x402_version=1,
            scheme=self.SCHEME_NAME,
            network=f"mvx:{self.chain_id}",
            payload=payload_dict
        )

    def _construct_esdt_data(self, token_identifier: str, amount: int) -> str:
        """
        Helper to construct ESDTTransfer data field.
        Format: ESDTTransfer@<TokenHex>@<AmountHex>
        """
        if token_identifier == "EGLD":
            return "" # EGLD transfer doesn't use data field for value
            
        # Token Identifier to Hex
        token_hex = token_identifier.encode().hex()
        
        # Amount to Hex (even length)
        # If amount is 0, it should be just "00" or empty? Typically "00" or logic handles it.
        # However, ESDTTransfer requires amount.
        amount_hex = hex(amount)[2:]
        if len(amount_hex) % 2 != 0:
            amount_hex = "0" + amount_hex
            
        return f"ESDTTransfer@{token_hex}@{amount_hex}"

    def resolve_did_to_address(self, did: str) -> str:
        """
        Resolves a did:pkh:multiversx:1:<bech32> to a bech32 address.
        """
        # Format: did:pkh:mvx:{chain_id}:{address}
        parts = did.split(":")
        if len(parts) >= 4 and parts[1] == "pkh" and parts[2] == "mvx":
             return parts[4]
        raise ValueError(f"Invalid MultiversX DID: {did}")
