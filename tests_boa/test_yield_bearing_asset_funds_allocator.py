import os
import pytest
import boa
from boa.util.abi import Address as Address
from decimal import Decimal
from dataclasses import dataclass, field
from itertools import chain
from typing import List, Dict

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
    def from_dict(cls, data: Dict[str, int]) -> "BalanceAdapter":
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
        {'exception': None, 'ratio_value': 100, 'target':1000, 'delta':0, 'leftovers':0, 'block': False, 'neutral': False}), # 0 : No transfer

    ({  'adapter': Address('0x0000000000000000000000000000000000000002'), 'current': 1500, 'last_value': 1500, 'max_deposit': 1000, 'ratio': 20 },
        {'exception': None, 'ratio_value': 100, 'target':2000, 'delta':500, 'leftovers':0, 'block': False, 'neutral': False}), # 1  : Deposit 500 normally

    ({  'adapter': Address('0x0000000000000000000000000000000000000003'), 'current': 2000, 'last_value': 1500, 'max_deposit': 1000, 'ratio': 15 },
        {'exception': None, 'ratio_value': 100, 'target':1500, 'delta':-500, 'leftovers':0, 'block': False, 'neutral': False}), # 2 : Withdraw 500 normally

    ({  'adapter': Address('0x0000000000000000000000000000000000000004'), 'current': 1500, 'last_value': 1500, 'max_deposit': 300, 'ratio': 20 },
        {'exception': None, 'ratio_value': 100, 'target':2000, 'delta':300, 'leftovers':200, 'block': False, 'neutral': False}), # 3 : Deposit 300 limited by max_deposit

    ({  'adapter': Address('0x0000000000000000000000000000000000000005'), 'current': 2000, 'last_value': 1500, 'max_withdraw': -300, 'ratio': 15 },
        {'exception': None, 'ratio_value': 100, 'target':1500, 'delta':-300, 'leftovers':-200, 'block': False, 'neutral': False}), # 4 : Withdraw 300 limited by max_withdraw

    ({  'adapter': Address('0x0000000000000000000000000000000000000006'), 'current': 1000, 'last_value': 900, 'max_deposit': neutral_max_deposit, 'ratio': 0 },
        {'exception': None, 'ratio_value': 100, 'target':0, 'delta':-1000, 'leftovers':0, 'block': False, 'neutral': True}), # 5 : Neutral adapter, Withdraw 1000.

    ({  'adapter': Address('0x0000000000000000000000000000000000000007'), 'current': 1000, 'last_value': 1500, 'ratio': 10 },
        {'exception': None, 'ratio_value': 100, 'target':0, 'delta':-1000, 'leftovers':0, 'block': True, 'neutral': False, 'new_ratio': 0}), # 6 : Loss! Withdraw 1000.

    ({  'adapter': Address('0x0000000000000000000000000000000000000008'), 'current': 500, 'last_value': 500, 'max_deposit': neutral_max_deposit, 'ratio': 5 },
        {'exception': None, 'ratio_value': 100, 'target':500, 'delta':0, 'leftovers':0, 'block': False, 'neutral': True}), # 7 : Neutral adapter, in balance.    
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


def _total_assets(buffer: int, adapter_states: List[BalanceAdapter] = []) -> int:
    result = buffer
    for adapter in adapter_states:
        result += adapter.current
    return result

def _total_ratios(adapter_states: List[BalanceAdapter] = []) -> int:
    result = 0
    for adapter in adapter_states:
        result += adapter.ratio
    return result

def _adapter_states(offset_list: List[int] = []) -> List[BalanceAdapter]:
    assert not len(offset_list) > MAX_ADAPTERS, "Too many adapters!"
    states = [BalanceAdapter.from_dict(balance_adapters_data[x][0]) for x in offset_list]
    return [x for x in chain(states, [BalanceAdapter()] * MAX_ADAPTERS)][:MAX_ADAPTERS]

def _txs(tx_list: List[tuple] = []) -> List[tuple]:
    """
    tx_list should be [(delta, offset into balance_adapters_data),]
    """
    assert not len(tx_list) > MAX_ADAPTERS, "Too many txs!"
    txs = [(x[0], BalanceAdapter.from_dict(balance_adapters_data[x[1]][0]).adapter) for x in tx_list]
    return [x for x in chain(txs, [(0, "0x0000000000000000000000000000000000000000")] * MAX_ADAPTERS)][:MAX_ADAPTERS]

def _blocked_adapters(adapter_list: List[int] = []) -> List[str]:
    adapters = [BalanceAdapter.from_dict(balance_adapters_data[x][0]).adapter for x in adapter_list]
    return [x for x in chain(adapters, ["0x0000000000000000000000000000000000000000"] * MAX_ADAPTERS)][:MAX_ADAPTERS]

# The adapters in these scenarios reference the offset of balance_adapters_data to select adapters.
tx_scenarios = [ # Deposit scenarios
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [0,5],
                  'tx_results': [(1000,0),], 'blocked': []}, # 1 - Standard deposit to primary adapter with neutral standby
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [5,0],
                  'tx_results': [(1000,0),], 'blocked': []}, # 2 - Standard deposit to primary adapter with neutral standby (reverse order)
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [5],
                  'tx_results': [(1000,5),], 'blocked': []}, # 3 - Deposit to neutral standby - no other adapters
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [],
                  'tx_results': [], 'blocked': []}, # 4 - Deposit with no adapters. Does nothing.
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [3,5],
                  'tx_results': [(300,3),(700,5)], 'blocked': []}, # 5 - Limited deposit to primary adapter with neutral taking the rest.
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [3],
                  'tx_results': [(300,3)], 'blocked': []}, # 6 - Limited deposit to primary adapter with rest staying in vault buffer no neutral adapter.
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [0,1,2,3,4],
                  'tx_results': [(1000,1)], 'blocked': []}, # 7 - Deposit satisfied by 1 because it is most out of balance for deposits, no neutreal adapter.
                 {'vault_balance': 1000, 'target_vault_balance': 0, 'min_payout': 0, 'adapters': [0,1,2,3,6],
                  'tx_results': [(-1000,6), (1000,1)], 'blocked': [6]}, # 8 - Blocked withdraw then original deposit satisfied by 1 because it is most out of balance for deposits, no neutreal adapter.

                # Withdraw scenarios satisfied by vault buffer
                {'vault_balance': 1000, 'target_vault_balance': 500, 'min_payout': 0, 'adapters': [],
                  'tx_results': [], 'blocked': []}, # 9 - Withdraw with no adapter but plenty of vault buffer so no tx.
                {'vault_balance': 1000, 'target_vault_balance': 500, 'min_payout': 0, 'adapters': [3,5],
                  'tx_results': [], 'blocked': []}, # 10 - Withdraw with normal adapter and neutral adapter but plenty of vault buffer so no tx.
                {'vault_balance': 1000, 'target_vault_balance': 500, 'min_payout': 0, 'adapters': [5],
                  'tx_results': [], 'blocked': []}, # 11 - Withdraw with neutral adapter but plenty of vault buffer so no tx.

                # Withdraw scenarios satisfied by adapter withdraws
                {'vault_balance': 200, 'target_vault_balance': 500, 'min_payout': 0, 'adapters': [5],
                  'tx_results': [(-300,5)], 'blocked': []}, # 12 - Withdraw with neutral adapter after draining vault buffer.
                {'vault_balance': 200, 'target_vault_balance': 500, 'min_payout': 0, 'adapters': [0, 5],
                  'tx_results': [(-300,5)], 'blocked': []}, # 13 - Withdraw with regular adapter & neutral adapter, satisfied exclusively by neutral adapter.
                {'vault_balance': 200, 'target_vault_balance': 500, 'min_payout': 0, 'adapters': [5, 0],
                  'tx_results': [(-300,5)], 'blocked': []}, # 14 - Withdraw with regular adapter & neutral adapter (rev order), satisfied exclusively by neutral adapter.

                {'vault_balance': 200, 'target_vault_balance': 500, 'min_payout': 0, 'adapters': [0],
                  'tx_results': [(-300,0)], 'blocked': []}, # 15 - Withdraw with regular adapter and no neutral adapter.
                {'vault_balance': 0, 'target_vault_balance': 1000, 'min_payout': 0, 'adapters': [0,1,2,3,4],
                  'tx_results': [(-1000,2)], 'blocked': []}, # 16 - Withdraw satisfied by 2 because it is most out of balance for withdraws, no neutreal adapter.
                {'vault_balance': 0, 'target_vault_balance': 1000, 'min_payout': 0, 'adapters': [1,2,3,4,7],
                  'tx_results': [(-500,7),(-500,2)], 'blocked': []}, # 17 - Withdraw partially satisified by 7 because it is the neutreal adapter then by 2 which is most out of balance.
                {'vault_balance': 0, 'target_vault_balance': 200, 'min_payout': 0, 'adapters': [1,2,3,4,7],
                  'tx_results': [(-200,7)], 'blocked': []}, # 18 - Withdraw satisfied by 7 because it is the neutreal adapter even though it is in balance and 2 is most out of balance.
                {'vault_balance': 0, 'target_vault_balance': 3000, 'min_payout': 0, 'adapters': [1,2,3,4,7],
                  'tx_results': [(-500,7),(-2000,2),(-500,1)], 'blocked': []}, # 19 - Withdraw satisfied by 7 (neutral), then 2 (out of balance), then 1 because it's simply next in line.
                {'vault_balance': 0, 'target_vault_balance': 4000, 'min_payout': 0, 'adapters': [1,2,6,4,7],
                  'tx_results': [(-1000,6), (-500,7),(-2000,2),(-500,1)], 'blocked': [6]}, # 20 - Withdraw satisfied by 6 (blocked), then 7 (neutral), then 2 (out of balance), then 1 because it's simply next in line.                  

                # Check for min_payout compliance.
                {'vault_balance': 10, 'target_vault_balance': 0, 'min_payout': 100, 'adapters': [0,5],
                  'tx_results': [], 'blocked': []}, # 21 - No tx because the min_payout for the deposit is larger than the vault_balance to deposit.
            ]

def test_generate_balance_txs(funds_alloc):
    count = 1
    for scenario in tx_scenarios:
        adapter_states = _adapter_states(scenario['adapters'])
        print("adapter_states = %s" % adapter_states)

        adapter_tuples = [x.to_tuple() for x in adapter_states]
        print("adapter_tuples = %s" % adapter_tuples)

        total_assets = _total_assets(scenario['vault_balance'],adapter_states)
        total_ratios = _total_ratios(adapter_states)

        print("total_assets = %s" % total_assets)
        print("total_ratios = %s" % total_ratios)

        good_result = _txs(scenario.get('tx_results',[]))
        blocked_result = _blocked_adapters(scenario.get('blocked',[]))
        txs, blocked_addresses = funds_alloc.generate_balance_txs(scenario['vault_balance'], scenario['target_vault_balance'], 
                                                                  scenario.get('min_payout',0), total_assets, total_ratios, adapter_tuples,
                                                                  scenario.get('withdraw_only',False), scenario.get('full_rebalance', False))

        print("\n***Scenario #%s***" % count)
        count += 1
        print("\ntxs = %s\ngood_result = %s\n" % (txs, good_result))
        print("blocked_addresses = %s" % blocked_addresses)
        assert txs == good_result
        assert blocked_addresses == blocked_result
