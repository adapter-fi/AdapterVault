import os
import pytest
import boa
from boa.util.abi import Address as Address
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
    adapter: Address
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

    def from_tuple(self, t):
        self.adapter = Address(t[0]),
        self.current = t[1],
        self.last_value = t[2],
        self.max_deposit = t[3],
        self.max_withdraw = t[4],
        self.ratio = t[5],
        self.target = t[6],
        self.delta = t[7]
                       

balance_adapters_data = [
    ({  'adapter': Address('0x0000000000000000000000000000000000000001'), 'current': 1000, 'last_value': 900, 'ratio': 10 },
        {'exception': None, 'ratio_value': 100, 'target':1000, 'delta':0, 'leftovers':0, 'block': False, 'neutral': False}),
    #({  'adapter': Address('0x0000000000000000000000000000000000000002'), 'current': 1500, 'last_value': 1500, 'max_deposit': 1000, 'ratio': 20 },
    #    {'exception': None, 'ratio_value': 100, 'target':2000, 'delta':500, 'leftovers':0, 'block': False, 'neutral': False}),
]

def test_allocate_balance_adapter_tx(funds_alloc):
    for adapter_data in balance_adapters_data:
        adapter = BalanceAdapter.from_dict(adapter_data[0])
        print("adapter = %s" % adapter)
        target_result = adapter_data[1]
        adapter_tuple = adapter.to_tuple()
        # result = funds_alloc.internal._allocate_balance_adapter_tx(100, adapter_tuple) # This fails with boa now.
        allocated_adapter, leftovers, block_adapter, neutral_adapter = funds_alloc.allocate_balance_adapter_tx(target_result['ratio_value'], adapter_tuple)
        print("allocated_adapter[0] = %s" % allocated_adapter[0])
        print("allocated_adapter[1] = %s" % allocated_adapter[1])
        print("type(allocated_adapter[0]) = %s" % type(allocated_adapter[0]))
        print("before type(adapter.adapter) = %s" % type(adapter.adapter))
        adapter.from_tuple(allocated_adapter)
        print("after type(adapter.adapter) = %s" % type(adapter.adapter))
        print("adapter.adapter = %s" % Address(adapter.adapter[0]))
        print("adapter_data[0]['adapter'] = %s" % adapter_data[0]['adapter'])
        print("type(adapter.adapter) = %s" % type(adapter.adapter))
        print("type(adapter_data[0]['adapter']) = %s" % type(adapter_data[0]['adapter']))        
        print("adapter.adapter == adapter_data[0]['adapter'] = %s" % adapter.adapter == adapter_data[0]['adapter'])
        assert Address(adapter.adapter[0]) == adapter_data[0]['adapter'] # BDM WTF?!?!? Why is adapter.adapter becoming a tuple????
        assert adapter.current == adapter_data[0]['current']
        adapter.target = target_result['target'] # 100 * adapter.ratio
        adapter.delta = target_result['delta'] # adapter.target - adapter.current
        #assert result == (adapter.to_tuple(), target_result['leftovers'], target_result['block'], target_result['neutral'])
