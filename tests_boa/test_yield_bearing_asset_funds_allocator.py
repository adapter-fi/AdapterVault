import os
import pytest
import boa
from decimal import Decimal
from dataclasses import dataclass, field

# ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
# MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy

@pytest.fixture
def deployer():
    acc = boa.env.generate_address(alias="deployer")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

# @pytest.fixture
# def trader():
#     acc = boa.env.generate_address(alias="trader")
#     boa.env.set_balance(acc, 1000*10**18)
#     return acc

# @pytest.fixture
# def dai(deployer, trader):
#     with boa.env.prank(deployer):
#         erc = boa.load("contracts/test_helpers/ERC20.vy", "DAI Token", "DAI", 18, 1000*10**18, deployer)
#         erc.mint(deployer, 100000)
#         erc.mint(trader, 100000)
#     return erc    

# @pytest.fixture
# def erc20(deployer, trader):
#     with boa.env.prank(deployer):
#         erc = boa.load("contracts/test_helpers/ERC20.vy", "ERC20", "Coin", 18, 1000*10**18, deployer)
#         erc.mint(deployer, 100000)
#         erc.mint(trader, 100000)
#     return erc     

@pytest.fixture
def funds_alloc(deployer):
    with boa.env.prank(deployer):
        f = boa.load("contracts/YieldBearingAssetFundsAllocator.vy")
    return f


def test_is_full_rebalance(funds_alloc):
    assert funds_alloc.internal._is_full_rebalance() == False


max_uint256 = 2**256 - 1
max_int256 = 2**255 - 1
min_uint256 = 0
min_int256 = -2**255
neutral_max_deposit = max_int256 - 42

@dataclass
class BalanceAdapter:
    adapter: str
    current: int = field(default=0)
    last_value: int = field(default=0)
    max_deposit: int = field(default=max_int256)
    max_withdraw: int = field(default=min_int256)
    ratio: int = field(default=0)
    target: int = field(default=0)
    delta: int = field(default=0)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)

    def to_tuple(self):
        return (
            self.adapter,
            self.current,
            self.last_value,
            self.max_deposit,
            self.max_withdraw,
            self.ratio,
            self.target,
            self.delta
        )        

balance_adapters_data = [
    {
        'adapter': '0x0000000000000000000000000000000000000001',
        'current': 1000,
        'last_value': 900,
        'ratio': 10
    },
    {
        'adapter': '0x0000000000000000000000000000000000000002',
        'current': 2000,
        'last_value': 1800,
        'max_deposit': 1000,
        'max_withdraw': -600,
        'ratio': 20,
        'target' : 2000,
        'delta' : 0
    },
]

def test_allocate_balance_adapter(funds_alloc):
    adapter = BalanceAdapter.from_dict(balance_adapters_data[0])
    adapter_tuple = adapter.to_tuple()
    result = funds_alloc.allocate_balance_adapter(0, adapter_tuple) 
    assert result == (adapter_tuple, 0, False)
