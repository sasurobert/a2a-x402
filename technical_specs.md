# Technical Specifications: MultiversX Integration for Google Agentic Commerce

## 1. Overview
This document specifies the integration of the **Agent Payments Protocol (AP2)** and the **A2A x402 Extension** with the **MultiversX Sovereign Blockchain**. The integration enables autonomous AI agents to perform secure, gasless, and cryptographically verifiable transactions.

## 2. Identity and addressing
Integration relies on **Chain Agnostic Improvement Proposals (CAIPs)** and **W3C Decentralized Identifiers (DIDs)**.

### 2.1 CAIP-2 Chain Identifiers
- **Namespace**: `mvx`
- **Mainnet**: `mvx:1`
- **Devnet**: `mvx:D`
- **Testnet**: `mvx:T`
- **CAIP-2 Registry**: [mvx/caip2](https://namespaces.chainagnostic.org/mvx/caip2)

### 2.2 DID Method (did:pkh)
MultiversX accounts are represented using the `did:pkh` method, wrapping the CAIP-10 identifier.
- **Format**: `did:pkh:mvx:{chain_Id}:{bech32_address}`
- **Example**: `did:pkh:mvx:1:erd1qyu5...`

## 3. Token Standards and Interaction
Payments utilize the native **Elrond Standard Digital Token (ESDT)** protocol.

### 3.1 ESDT Transfer Format
Transaction `data` field must follow the standard `MultiESDTNFTTransfer` format for ESDTs:
`MultiESDTNFTTransfer@<ReceiverHex>@01@<TokenIdentifierHex>@00@<AmountHex>[@<FunctionHex>@<ArgHex>...]`

For native EGLD, `data` is empty unless a smart contract function is specified.

### 3.2 Feature Matrix (Alignment with TS/Go)
| Feature | Implementation Detail |
|---------|-----------------------|
| **Versioning** | `version: 1` (Direct), `version: 2` (Relayed V3) |
| **Relayer** | Required for `version: 2`; Credential Provider pays gas. |
| **Transaction Expiry** | `validAfter` (now - 600s), `validBefore` (now + custom/600s). |
| **Gas Calculation** | `50,000 + 1,500 * len(data) + 200,000 + 50,000` (Base + Bytes + MultiTransfer + Relayed). |
| **Validation** | Bech32 (erd1...), TokenID (`^[A-Z0-9]{3,8}-[0-9a-fA-F]{6}$`). |
| **Money Parsing** | Flexible parsing of strings/floats to EGLD (18 decimals). |

## 4. MultiversX Python Implementation (SDK v2)
The implementation will follow the **Controller/Factory** pattern recommended for `multiversx-sdk` v2.

### 4.1 Client Implementation (Payment Creation)
- Use `TransferTransactionsFactory` to construct the unsigned transaction.
- Use `TransactionsFactoryConfig` initialized with the correct `chain_id`.
- Manually sign using the provided `MultiversXSigner`.

### 4.2 Server Implementation (Verification & Enhancement)
- `parse_price`: Converts input amounts to atomic units.
- `enhance_payment_requirements`: Injects default `gas_limit` and `asset_transfer_method` (direct vs. esdt).
- `validate_payment_requirements`: Enforces strictly valid addresses and tokens.

## 5. x402 Scheme Implementation (Python)
The `MultiversXScheme` class in `a2a-x402` implements the functional core of the payment rail.

### 5.1 Core Interface
- `create_payment_requirements`: Generates the x402 "Payment Required" payload.
- `construct_payment_payload`: Constructs the inner transaction and collects the agent's signature.
- `verify_transaction_content`: (To be implemented) Off-chain verification of a completed transaction against the original request.

## 6. Security and Compliance
- **Key Management**: Private keys MUST NEVER be stored in the A2A library. Signing is delegated to specialized `UserSigner` or HSM environments.
- **Data Privacy**: No PII (names, addresses) shall be written to the blockchain. The `data` field should only contain a hash of the Cart Mandate if needed.

## 7. Dependencies
- `multiversx-sdk >= 2.0.0`
