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

import os
from dataclasses import dataclass

@dataclass
class MultiversXConfig:
    """
    Centralized configuration for MultiversX (mvx) protocol constants.
    Values are aligned with the 'Exact' scheme implementation logic.
    """
    GAS_BASE_COST: int = 50000
    GAS_PER_BYTE: int = 1500
    GAS_MULTI_TRANSFER_COST: int = 200000
    GAS_RELAYED_COST: int = 50000
    GAS_PRICE_DEFAULT: int = 1000000000
    
    TRANSFER_METHOD_DIRECT: str = "direct"
    TRANSFER_METHOD_ESDT: str = "esdt"
    
    # Validation
    DEFAULT_TIMEOUT_SECONDS: int = 600
    MIN_TIMEOUT_SECONDS: int = 60
    
    # Chain Agnostic
    CAIP2_NAMESPACE: str = "mvx"

    @classmethod
    def from_env(cls) -> "MultiversXConfig":
        return cls(
            GAS_BASE_COST=int(os.getenv("MVX_GAS_BASE_COST", 50000)),
            GAS_PER_BYTE=int(os.getenv("MVX_GAS_PER_BYTE", 1500)),
            GAS_MULTI_TRANSFER_COST=int(os.getenv("MVX_GAS_MULTI_TRANSFER_COST", 200000)),
            GAS_RELAYED_COST=int(os.getenv("MVX_GAS_RELAYED_COST", 50000)),
            GAS_PRICE_DEFAULT=int(os.getenv("MVX_GAS_PRICE_DEFAULT", 1000000000)),
            DEFAULT_TIMEOUT_SECONDS=int(os.getenv("MVX_DEFAULT_TIMEOUT_SECONDS", 600)),
            MIN_TIMEOUT_SECONDS=int(os.getenv("MVX_MIN_TIMEOUT_SECONDS", 60)),
        )
