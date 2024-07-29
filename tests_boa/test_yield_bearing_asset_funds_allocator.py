import os
import pytest
import boa
from boa.util.abi import Address as Address
from decimal import Decimal
from dataclasses import dataclass, field
from itertools import chain

# ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy

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
    adapter: Address = field(default=Address('0x0000000000000000000000000000000000000001'))
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
        {'exception': None, 'ratio_value': 100, 'target':1000, 'delta':0, 'leftovers':0, 'block': False, 'neutral': False}), # No transfer

    ({  'adapter': Address('0x0000000000000000000000000000000000000002'), 'current': 1500, 'last_value': 1500, 'max_deposit': 1000, 'ratio': 20 },
        {'exception': None, 'ratio_value': 100, 'target':2000, 'delta':500, 'leftovers':0, 'block': False, 'neutral': False}), # Deposit 500 normally

    ({  'adapter': Address('0x0000000000000000000000000000000000000003'), 'current': 2000, 'last_value': 1500, 'max_deposit': 1000, 'ratio': 15 },
        {'exception': None, 'ratio_value': 100, 'target':1500, 'delta':-500, 'leftovers':0, 'block': False, 'neutral': False}), # Withdraw 500 normally

    ({  'adapter': Address('0x0000000000000000000000000000000000000005'), 'current': 1500, 'last_value': 1500, 'max_deposit': 300, 'ratio': 20 },
        {'exception': None, 'ratio_value': 100, 'target':2000, 'delta':300, 'leftovers':200, 'block': False, 'neutral': False}), # Deposit 300 limited by max_deposit

    ({  'adapter': Address('0x0000000000000000000000000000000000000005'), 'current': 2000, 'last_value': 1500, 'max_withdraw': -300, 'ratio': 15 },
        {'exception': None, 'ratio_value': 100, 'target':1500, 'delta':-300, 'leftovers':-200, 'block': False, 'neutral': False}), # Withdraw 300 limited by max_withdraw

    ({  'adapter': Address('0x0000000000000000000000000000000000000006'), 'current': 1000, 'last_value': 900, 'max_deposit': neutral_max_deposit, 'ratio': 0 },
        {'exception': None, 'ratio_value': 100, 'target':0, 'delta':-1000, 'leftovers':0, 'block': False, 'neutral': True}), # Neutral adapter, Withdraw 1000.

    ({  'adapter': Address('0x0000000000000000000000000000000000000007'), 'current': 1000, 'last_value': 1500, 'ratio': 10 },
        {'exception': None, 'ratio_value': 100, 'target':0, 'delta':-1000, 'leftovers':0, 'block': True, 'neutral': False, 'new_ratio': 0}), # Loss! Withdraw 1000.
]

def test_allocate_balance_adapter_tx(funds_alloc):
    counter = 0
    for adapter_data in balance_adapters_data:
        adapter = BalanceAdapter.from_dict(adapter_data[0])
        print("adapter[%s] = %s" % (counter,adapter))
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
        assert adapter.current[0] == adapter_data[0]['current']
        assert adapter.last_value[0] == adapter_data[0]['last_value']
        assert adapter.ratio[0] == adapter_data[1].get('new_ratio', adapter_data[0]['ratio'])
        assert adapter.target[0] == adapter_data[1]['target']
        assert adapter.delta == adapter_data[1]['delta']
        assert leftovers == adapter_data[1]['leftovers']
        assert block_adapter == adapter_data[1]['block']
        assert neutral_adapter == adapter_data[1]['neutral']
        counter += 1


def _total_assets(buffer, adapter_states):
    result = buffer
    for adapter in adapter_states:
        result += adapter.current
    return result

def _total_ratios(adapter_states):
    result = 0
    for adapter in adapter_states:
        result += adapter.ratio

def _adapter_states(offset_list):
    states = [BalanceAdapter.from_dict(balance_adapters_data[x][0]) for x in offset_list]
    return [x for x in chain(states, [BalanceAdapter()] * MAX_ADAPTERS)][:MAX_ADAPTERS]

def _txs(tx_list):
    return [x for x in chain(tx_list, [(0, Address('0x0000000000000000000000000000000000000000'))] * MAX_ADAPTERS )][:MAX_ADAPTERS]

def test_generate_balance_txs(funds_alloc):
    adapter_states = _adapter_states([0,5])
    print("adapter_states = %s" % adapter_states)

    adapter_tuples = [x.to_tuple() for x in adapter_states]
    print("adapter_tuples = %s" % adapter_tuples)

    total_assets = _total_assets(1000,adapter_states)
    total_ratios = _total_ratios(adapter_states)

    print("total_assets = %s" % total_assets)
    print("total_ratios = %s" % total_ratios)

    good_result = _txs([(1000, Address('0x0000000000000000000000000000000000000001'))])
    txs, blocked_addresses = funds_alloc.generate_balance_txs(1000, 0, 0, total_assets, 10, adapter_tuples, False)

    print("txs = %s" % txs)
    print("blocked_addresses = %s" % blocked_addresses)
    assert txs == good_result
