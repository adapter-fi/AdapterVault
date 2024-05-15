"""
## [H-01] Access control modifiers on _claim_fees will permanently lock proposer

### Details 

[AdapterVault.vy#L519-L521](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/AdapterVault.vy#L519-L521)

    elif _yield == FeeType.PROPOSER:
        assert msg.sender == self.current_proposer, "Only curent proposer may claim strategy fees."
        self.total_strategy_fees_claimed += claim_amount        

AdapterVault#_set_strategy attempts to distribute fees to proposer when proposer changes. The problem is that _claim_fees requires that msg.sender == proposer. Since _set_strategy can only be called by governance this subcall will always revert. The result is that the first proposer will have a monopoly on all proposals since any strategy that wasn't submitted by them would fail when attempting to activate it.

### Lines of Code

https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/AdapterVault.vy#L496-L533

### Recommendation

Revise access control on _set_strategy. I would suggest allowing anyone to claim tokens but sending to the correct target instead of msg.sender
"""
import copy
from dataclasses import dataclass

import pytest
import ape
from tests.conftest import is_not_hard_hat

from itertools import zip_longest
MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy

d4626_name = "DynamoDAI"
d4626_token = "dyDAI"
d4626_decimals = 18

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def strategizer1(accounts):
    return accounts[2]

@pytest.fixture
def strategizer2(accounts):
    return accounts[3]

@pytest.fixture
def dai(project, deployer, trader):
    ua = deployer.deploy(project.ERC20, "DAI", "DAI", 18, 0, deployer)
    #Transfer some to trader.
    ua.mint(trader, 1000000000, sender=deployer)
    return ua

@pytest.fixture
def funds_alloc(project, deployer):
    f = deployer.deploy(project.FundsAllocator)
    return f

def _setup_single_adapter(_project, _AdapterVault, _deployer, _dai, _adapter, strategizer, ratio=1):
    # Setup our adapter strategy first.
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 

    # Get the current strategy settings.
    pos = 0
    for adapter in _AdapterVault.adapter_list():
        strategy[pos] = (adapter, _AdapterVault.strategy(adapter).ratio)
        pos += 1

    strategy[pos] = (_adapter.address,ratio)
    print("strategy for _setup_single_adapter: %s." % strategy)
    _AdapterVault.set_strategy(strategizer, strategy, 0, sender=_deployer)

    # Now add the adapter.
    _AdapterVault.add_adapter(_adapter, sender=_deployer)    

    # Jiggle around transfer rights here for test purposes.
    werc20 = _project.ERC20.at(_adapter.wrappedAsset())
    if werc20.minter() != _AdapterVault:
        werc20.transferMinter(_AdapterVault, sender=_deployer)
    werc20.setApprove(_adapter, _AdapterVault, (1<<256)-1, sender=_AdapterVault) 
    _dai.setApprove(_AdapterVault, _adapter, (1<<256)-1, sender=_deployer)
    _dai.setApprove(_adapter, _AdapterVault, (1<<256)-1, sender=_deployer)


@pytest.fixture
def adapter_adapterA(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "aWDAI", "aWDAI", 18, 0, deployer)
    a = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return a

@pytest.fixture
def AdapterVault(project, deployer, dai, trader, funds_alloc):
    v = deployer.deploy(project.AdapterVault, d4626_name, d4626_token, d4626_decimals, dai, [], deployer, funds_alloc, "2.0")    
    return v

#Setup the most minimalist vault...
def test_set_acl_claim_fees(project, deployer, AdapterVault, adapter_adapterA, dai, trader, strategizer1, strategizer2):
    #setup adapter with a different proposer and governance.
    _setup_single_adapter(project,AdapterVault, deployer, dai, adapter_adapterA, strategizer1)
    #Cause some activity and yield so that there is claimable fees accrued
   
    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(AdapterVault,1000, sender=trader)
    AdapterVault.deposit(1000, trader, sender=trader)
    assert AdapterVault.maxWithdraw(trader) == 1000

    #cause some yield
    # Increase assets in adapter so its assets will double.
    dai.mint(adapter_adapterA, 1000, sender=deployer)
    assert AdapterVault.maxWithdraw(trader) > 1000

    assert AdapterVault.claimable_strategy_fees_available() > AdapterVault.min_proposer_payout(), "Not enough to pay Strategist!"

    print("AdapterVault.claimable_strategy_fees_available() : %s." % AdapterVault.claimable_strategy_fees_available())
    print("AdapterVault.claimable_yield_fees_available() : %s." % AdapterVault.claimable_yield_fees_available())
    print("AdapterVault.claimable_all_fees_available() : %s." % AdapterVault.claimable_all_fees_available())
    print("Minimum strategy payout: %s." % AdapterVault.min_proposer_payout())


    #No issues if new strategy is from the same proposer
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS
    strategy[0] = (adapter_adapterA.address, 1)

    strategizer = AdapterVault.current_proposer()
    assert strategizer == strategizer1, "Not same strategizer!"
    assert strategizer != strategizer2, "Same strategizer!"

    current_strat_funds = dai.balanceOf(strategizer)
    print("current_strat_funds : %s." % current_strat_funds)

    current_owner_funds = dai.balanceOf(AdapterVault.owner())
    print("current_owner_funds : %s." % current_owner_funds)  

    assert AdapterVault.claimable_strategy_fees_available() == 10, "Strat fees all wrong #1!"      

    AdapterVault.set_strategy(strategizer, strategy, AdapterVault.min_proposer_payout(), sender=deployer)

    assert AdapterVault.claimable_strategy_fees_available() == 10, "Strat fees all wrong #2!"

    #Per the audit report, if proposer fees claimable > min_proposer_payout, then governance cannot change the strategy...
    AdapterVault.set_strategy(strategizer2, strategy, AdapterVault.min_proposer_payout(), sender=deployer)

    updated_strat_funds = dai.balanceOf(strategizer)

    print("updated_strat_funds : %s." % updated_strat_funds)

    print("AdapterVault.claimable_strategy_fees_available() : %s." % AdapterVault.claimable_strategy_fees_available())
    print("AdapterVault.claimable_yield_fees_available() : %s." % AdapterVault.claimable_yield_fees_available())
    print("AdapterVault.claimable_all_fees_available() : %s." % AdapterVault.claimable_all_fees_available())
    

    assert updated_strat_funds > current_strat_funds, "strategizer didn't get paid!"

    AdapterVault.claim_all_fees(sender=deployer)

    updated_owner_funds = dai.balanceOf(AdapterVault.owner())

    print("updated_owner_funds : %s." % updated_owner_funds)

    assert updated_owner_funds > current_owner_funds, "owner didn't get paid!"

    print("AdapterVault.claimable_strategy_fees_available() : %s." % AdapterVault.claimable_strategy_fees_available())
    print("AdapterVault.claimable_yield_fees_available() : %s." % AdapterVault.claimable_yield_fees_available())
    print("AdapterVault.claimable_all_fees_available() : %s." % AdapterVault.claimable_all_fees_available())

