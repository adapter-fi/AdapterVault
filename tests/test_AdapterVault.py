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
def dai(project, deployer, trader):
    ua = deployer.deploy(project.ERC20, "DAI", "DAI", 18, 0, deployer)
    #Transfer some to trader.
    ua.mint(trader, 1000000000, sender=deployer)
    return ua


@pytest.fixture
def adapter_adapterA(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "aWDAI", "aWDAI", 18, 0, deployer)
    a = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return a


@pytest.fixture
def adapter_adapterB(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "bWDAI", "bWDAI", 18, 0, deployer)
    b = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return b


@pytest.fixture
def adapter_adapterC(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "cWDAI", "cWDAI", 18, 0, deployer)
    c = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return c    

@pytest.fixture
def funds_alloc(project, deployer):
    f = deployer.deploy(project.FundsAllocator)
    return f

@pytest.fixture
def adaptervault(project, deployer, dai, trader, funds_alloc):
    v = deployer.deploy(project.AdapterVault, d4626_name, d4626_token, d4626_decimals, dai, [], deployer, funds_alloc, "2.0")
    return v


# tx is an ape.Result
# event_names is an in-order list of strings of the names of the events generated in the tx.
# if full_match == True, event_names must match all result events.
# if full_match == False, we only check as many events as the event_names list has and ignore 
#                         extra event logs that may exist in tx.
def events_in_logs(tx, event_names, full_match=True) -> bool:
    for a,b in zip_longest(tx.decode_logs(), event_names):
        if b == None and full_match == False: continue
        assert a.event_name == b
    return True    


def test_basic_initialization(project, deployer, adaptervault):
    assert adaptervault.name(sender=deployer) == d4626_name
    assert adaptervault.symbol(sender=deployer) == d4626_token
    assert adaptervault.decimals(sender=deployer) == d4626_decimals


def test_initial_adapters_initialization(project, deployer, dai, adapter_adapterA, adapter_adapterB, adapter_adapterC, funds_alloc):
    adapters = [adapter_adapterA, adapter_adapterB, adapter_adapterC]
    adapter_vault = deployer.deploy(project.AdapterVault, d4626_name, d4626_token, d4626_decimals, dai, adapters, deployer, funds_alloc, "2.0")    

    # This should fail because we can't add the same adapter twice!
    for adapter in adapters:
        # can't add it a second time.
        with ape.reverts("adapter already supported."):
            adapter_vault.add_adapter(adapter, sender=deployer)

    adapter_count = len(adapter_vault.adapter_list())
    assert adapter_count == 3


def test_add_adapter(project, deployer, adaptervault, adapter_adapterA, trader, dai):

    adapter_count = len(adaptervault.adapter_list())
    assert adapter_count == 0

    # adapter_adapterA can only be added by the owner.
    with ape.reverts("Only owner can add new Lending Adapters."):
        result = adaptervault.add_adapter(adapter_adapterA, sender=trader)

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")
    # adapter_adapterA is valid & deployer is allowed to add it.
    result = adaptervault.add_adapter(adapter_adapterA, sender=deployer) 
    assert result.return_value == True
    assert events_in_logs(result, ["AdapterAdded"])

    # can't add it a second time.
    with ape.reverts("adapter already supported."):
        result = adaptervault.add_adapter(adapter_adapterA, sender=deployer)

    # dai is not a valid adapter.
    # BDM - this protection makes our contract too large to deploy!
    #with ape.reverts("Doesn't appear to be an LPAdapter."):    
    #    result = adaptervault.add_adapter(dai, sender=deployer) 
    
    adapter_count = len(adaptervault.adapter_list())
    assert adapter_count == 1

    # How many more adapters can we add?
    for i in range(MAX_ADAPTERS - 1): 
        a = deployer.deploy(project.MockLPAdapter, dai, dai)
        result = adaptervault.add_adapter(a, sender=deployer) 
        assert result.return_value == True
        assert events_in_logs(result, ["AdapterAdded"])

    # One more adapter is too many however.
    a = deployer.deploy(project.MockLPAdapter, dai, dai)
    with ape.reverts():
        adaptervault.add_adapter(a, sender=deployer)


def _setup_single_adapter(_project, _adaptervault, _deployer, _dai, _adapter, ratio=1):
    # Setup our adapter strategy first.
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 

    # Get the current strategy settings.
    pos = 0
    for adapter in _adaptervault.adapter_list():
        strategy[pos] = (adapter, _adaptervault.strategy(adapter).ratio)
        pos += 1

    strategy[pos] = (_adapter.address,ratio)
    print("strategy for _setup_single_adapter: %s." % strategy)
    _adaptervault.set_strategy(_deployer, strategy, 0, sender=_deployer)

    # Now add the adapter.
    _adaptervault.add_adapter(_adapter, sender=_deployer)    

    # Jiggle around transfer rights here for test purposes.
    werc20 = _project.ERC20.at(_adapter.wrappedAsset())
    if werc20.minter() != _adaptervault:
        werc20.transferMinter(_adaptervault, sender=_deployer)
    werc20.setApprove(_adapter, _adaptervault, (1<<256)-1, sender=_adaptervault) 
    _dai.setApprove(_adaptervault, _adapter, (1<<256)-1, sender=_deployer)
    _dai.setApprove(_adapter, _adaptervault, (1<<256)-1, sender=_deployer)


def test_remove_adapter(project, deployer, adaptervault, adapter_adapterA, adapter_adapterB, trader, dai):
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterA)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,1000, sender=trader)

    assert adaptervault.totalAssets() == 0
    assert adapter_adapterA.totalAssets() == 0  
    assert adapter_adapterA in adaptervault.adapter_list()

    assert adaptervault.try_total_assets(sender=trader).return_value == 0

    result = adaptervault.deposit(500, trader, sender=trader)

    assert adaptervault.totalAssets() == 500   
    # BDM FIX! assert adapter_adapterA.totalAssets() == 500

    with ape.reverts("Only owner can remove Lending Adapters."):
        result = adaptervault.remove_adapter(adapter_adapterA, sender=trader)

    result = adaptervault.remove_adapter(adapter_adapterA, sender=deployer)

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    assert result.return_value == True

    assert adaptervault.totalAssets() == 500   
    assert adapter_adapterA.totalAssets() == 0    
    assert adapter_adapterA not in adaptervault.adapter_list()

    print("HERE 1")

    assert adaptervault.totalAssets() == 500   
    assert adapter_adapterB.totalAssets() == 0

    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterB)

    print("HERE 2")

    assert adaptervault.totalAssets() == 500   

    # BDM ?!?!? Why does this fail ?!?!?!
    #assert adapter_adapterB.totalAssets() == 0

    print("HERE 3")

    adaptervault.balanceAdapters(0, _max_txs = MAX_ADAPTERS, sender=deployer)

    print("HERE 4")

    assert adaptervault.totalAssets() == 500   
    assert adapter_adapterB.totalAssets() == 500

    print("HERE 5")

    result = adaptervault.remove_adapter(adapter_adapterB, False, sender=deployer) 
       
    print("HERE 6")

    assert result.return_value == True

    assert adaptervault.totalAssets() == 500   
    assert adapter_adapterB.totalAssets() == 0 


def test_min_tx_sizes(project, deployer, adaptervault, adapter_adapterA, trader, dai):
    pytest.skip("TODO: Not implemented yet.")    


def test_single_adapter_deposit(project, deployer, adaptervault, adapter_adapterA, dai, trader):
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterA)

    d4626_start_DAI = dai.balanceOf(adaptervault)
    LP_start_DAI = dai.balanceOf(adapter_adapterA)

    trade_start_DAI = project.ERC20.at(adapter_adapterA.originalAsset()).balanceOf(trader)
    trade_start_dyDAI = adaptervault.balanceOf(trader)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,1000, sender=trader)

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    assert adaptervault.totalAssets() == 0
    assert adapter_adapterA.totalAssets() == 0
    
    assert adaptervault.convertToShares(55) == 55
    assert adaptervault.convertToAssets(75) == 75

    assert adaptervault.try_total_assets(sender=trader).return_value == 0

    result = adaptervault.deposit(500, trader, sender=trader)
    print("GAS USED FOR DEPOSIT = ", result.gas_used) 

    assert adaptervault.totalAssets() == 500   
    assert adapter_adapterA.totalAssets() == 500     

    #print("result.return_value = ", result.return_value)
    #assert result.return_value == 500        

    assert adaptervault.balanceOf(trader) == 500

    assert adaptervault.convertToAssets(75) == 75
    assert adaptervault.convertToShares(55) == 55    

    trade_end_DAI = project.ERC20.at(adapter_adapterA.originalAsset()).balanceOf(trader)
    trade_end_dyDAI = adaptervault.balanceOf(trader)

    assert trade_start_DAI - trade_end_DAI == 500
    assert trade_end_dyDAI - trade_start_dyDAI == 500
    
    d4626_end_DAI = dai.balanceOf(adaptervault)

    # DAI should have just passed through the 4626 adapter.
    assert d4626_end_DAI == d4626_start_DAI

    LP_end_DAI = dai.balanceOf(adapter_adapterA)
    assert LP_end_DAI - LP_start_DAI == 500

    # Now do it again!
    result = adaptervault.deposit(400, trader, sender=trader)
    # BDM - tooling can't make the trace for the return_value.
    #assert result.return_value == 400     
    print("GAS USED FOR DEPOSIT = ", result.gas_used) 

    assert adaptervault.balanceOf(trader) == 900

    trade_end_DAI = project.ERC20.at(adapter_adapterA.originalAsset()).balanceOf(trader)
    trade_end_dyDAI = adaptervault.balanceOf(trader)

    assert trade_start_DAI - trade_end_DAI == 900
    assert trade_end_dyDAI - trade_start_dyDAI == 900
    
    d4626_end_DAI = dai.balanceOf(adaptervault)

    # DAI should have just passed through the 4626 adapter.
    assert d4626_end_DAI == d4626_start_DAI

    LP_end_DAI = dai.balanceOf(adapter_adapterA)
    assert LP_end_DAI - LP_start_DAI == 900

# Order of BalanceAdapter struct fields from AdapterVault
ADAPTER = 0
CURRENT = 1
LAST_VALUE = 2
RATIO = 3
TARGET = 4
DELTA = 5


def test_single_getBalanceTxs(project, deployer, adaptervault, adapter_adapterA, dai, trader):
    print("**** test_single_getBalanceTxs ****")
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterA)

    print("\nadapter setup complete.")
    assert adapter_adapterA.totalAssets() == 0
    assert adaptervault.totalAssets() == 0

    d4626_assets, adapters, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    assert adapters[0].current == 0    
    assert adapters[0].ratio == 1 
    assert total_assets == 0
    assert total_ratios == 1

    print("adapters = %s." % [x for x in adapters])

    total_assets = 1000
    adapter_asset_allocation, d4626_delta, tx_count, adapters, blocked_adapters = adaptervault.getTargetBalances(0, total_assets, total_ratios, adapters, 0)
    assert adapter_asset_allocation == 1000    
    assert d4626_delta == -1000
    assert tx_count == 1
    assert adapters[0].current == 0    
    assert adapters[0].ratio == 1 
    assert adapters[0].target == 1000
    assert adapters[0].delta == 1000

    print("adapters = %s." % [x for x in adapters])    


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,1000, sender=trader)

    result = adaptervault.deposit(1000, trader, sender=trader)

    d4626_assets, adapters, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    assert adapters[0].current == 1000
    assert adapters[0].ratio == 1 
    assert adapters[0].target == 0
    assert adapters[0].delta== 0
    assert total_assets == 1000
    assert total_ratios == 1    

    print("adapters = %s." % [x for x in adapters])

    adapter_asset_allocation, d4626_delta, tx_count, adapters, blocked_adapters = adaptervault.getTargetBalances(250, total_assets, total_ratios, adapters, 0)
    assert adapter_asset_allocation == 750
    assert d4626_delta == 250
    assert tx_count == 1
    assert adapters[0].current == 1000    
    assert adapters[0].ratio == 1 
    assert adapters[0].target == 750
    assert adapters[0].delta== -250

    print("adapters = %s." % [x for x in adapters])


def test_multiple_adapter_balanceAdapters(project, deployer, adaptervault, adapter_adapterA, adapter_adapterB, adapter_adapterC, dai, trader):
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterA)

    print("\nadapter setup complete.")
    assert adapter_adapterA.totalAssets() == 0
    assert adaptervault.totalAssets() == 0

    d4626_assets, adapters, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    assert adapters[0].current == 0    
    assert adapters[0].ratio == 1 
    assert total_assets == 0
    assert total_ratios == 1

    print("adapters = %s." % [x for x in adapters])

    total_assets = 1000
    adapter_asset_allocation, d4626_delta, tx_count, adapters, blocked_adapters = adaptervault.getTargetBalances(0, total_assets, total_ratios, adapters, 0)
    assert adapter_asset_allocation == 1000    
    assert d4626_delta == -1000
    assert tx_count == 1
    assert adapters[0].current == 0    
    assert adapters[0].ratio == 1 
    assert adapters[0].target == 1000
    assert adapters[0].delta == 1000

    print("adapters = %s." % [x for x in adapters])    


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,1000, sender=trader)

    result = adaptervault.deposit(1000, trader, sender=trader)

    d4626_assets, adapters, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    assert adapters[0].current == 1000
    assert adapters[0].ratio == 1 
    assert adapters[0].target == 0
    assert adapters[0].delta== 0
    assert total_assets == 1000
    assert total_ratios == 1    

    # Add a second adapter.
    _setup_single_adapter(project, adaptervault, deployer, dai, adapter_adapterB)

    adaptervault.balanceAdapters(0, _max_txs = MAX_ADAPTERS, sender=deployer)

    d4626_assets, adapters, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    
    assert adapters[0].adapter == adapter_adapterA
    assert adapters[0].current == 500
    assert adapters[0].ratio == 1 
    assert adapters[0].target == 0
    assert adapters[0].delta== 0

    assert adapters[1].adapter == adapter_adapterB
    assert adapters[1].current == 500
    assert adapters[1].ratio == 1 
    assert adapters[1].target == 0
    assert adapters[1].delta== 0    

    assert total_assets == 1000
    assert total_ratios == 2

    # Change the ratios for the strategy.
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS
    strategy[0] = (adapter_adapterA.address, 1)
    strategy[1] = (adapter_adapterB.address, 3)

    #strategy[0] = stratA
    #strategy[1] = stratB

    adaptervault.set_strategy(adaptervault.current_proposer(), strategy, adaptervault.min_proposer_payout(), sender=deployer)

    with ape.reverts("only owner can call balanceAdapters"):
        adaptervault.balanceAdapters(0, _max_txs = MAX_ADAPTERS, sender=trader)

    adaptervault.balanceAdapters(0, _max_txs = MAX_ADAPTERS, sender=deployer)

    d4626_assets, adapters, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    
    assert adapters[0].adapter == adapter_adapterA
    assert adapters[0].current == 250
    assert adapters[0].ratio == 1 
    assert adapters[0].target == 0
    assert adapters[0].delta== 0

    assert adapters[1].adapter == adapter_adapterB
    assert adapters[1].current == 750
    assert adapters[1].ratio == 3 
    assert adapters[1].target == 0
    assert adapters[1].delta== 0    

    assert total_assets == 1000
    assert total_ratios == 4

    # Change the ratios for the strategy.
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS
    strategy[0] = (adapter_adapterA.address, 3)
    strategy[1] = (adapter_adapterB.address, 1)

    #strategy[0] = stratA
    #strategy[1] = stratB

    adaptervault.set_strategy(adaptervault.current_proposer(), strategy, adaptervault.min_proposer_payout(), sender=deployer)

    adaptervault.balanceAdapters(0, _max_txs = MAX_ADAPTERS, sender=deployer)

    d4626_assets, adapters, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    
    assert adapters[0].adapter == adapter_adapterA
    assert adapters[0].current == 750
    assert adapters[0].ratio == 3 
    assert adapters[0].target == 0
    assert adapters[0].delta== 0

    assert adapters[1].adapter == adapter_adapterB
    assert adapters[1].current == 250
    assert adapters[1].ratio == 1 
    assert adapters[1].target == 0
    assert adapters[1].delta== 0    

    assert total_assets == 1000
    assert total_ratios == 4    


def test_single_adapter_withdraw(project, deployer, adaptervault, adapter_adapterA, dai, trader):
    _setup_single_adapter(project, adaptervault, deployer, dai, adapter_adapterA)

    assert adapter_adapterA.totalAssets() == 0
    assert adaptervault.totalAssets() == 0


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,1000, sender=trader)

    result = adaptervault.deposit(1000, trader, sender=trader)

    assert adapter_adapterA.totalAssets() == 1000
    assert adaptervault.totalAssets() == 1000

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    # BDM - tooling won't let us get the trace from this return_value
    #print("adaptervault.deposit(1000, trader, sender=trader) = %s." % result.return_value)
    #assert result.return_value == 1000   


    # There have been no earnings so shares & assets should map 1:1.
    assert adaptervault.convertToShares(250) == 250  
    assert adaptervault.convertToAssets(250) == 250  

    result = adaptervault.withdraw(250, trader, trader, 0, sender=trader)

    assert adapter_adapterA.totalAssets() == 750
    assert adaptervault.totalAssets() == 750

    assert result.return_value == 250


def test_single_adapter_share_value_increase(project, deployer, adaptervault, adapter_adapterA, dai, trader):
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterA)

    assert dai.balanceOf(trader) == 1000000000 

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,1000, sender=trader)

    assert dai.balanceOf(adaptervault) == 0

    adaptervault.deposit(1000, trader, sender=trader)

    assert dai.balanceOf(adaptervault) == 0
    assert dai.balanceOf(adapter_adapterA) == 1000

    assert dai.balanceOf(trader) == 1000000000 - 1000

    assert adaptervault.totalSupply() == 1000

    assert adaptervault.totalAssets() == 1000

    # Increase assets in adapter so its assets will double.
    dai.mint(adapter_adapterA, 1000, sender=deployer)

    assert dai.balanceOf(adapter_adapterA) == 2000    

    assert adaptervault.totalSupply() == 1000

    assert adaptervault.totalAssets() == 2000

    print("adaptervault.totalReturns() is %s." % adaptervault.totalReturns())
    assert adaptervault.totalReturns() == 1000

    # Assumes YIELD_FEE_PERCENTAGE : constant(decimal) = 10.0
    #     and PROPOSER_FEE_PERCENTAGE : constant(decimal) = 1.0

    print("adaptervault.claimable_all_fees_available() is %s." % adaptervault.claimable_all_fees_available())
    assert adaptervault.claimable_all_fees_available() == 110
    
    print("adaptervault.convertToAssets(1000) is :%s but should be: %s." % (int(adaptervault.convertToAssets(1000)),1000 + (1000 - (1000*0.11))))
    assert adaptervault.convertToAssets(1000) == 1000 + (1000 - (1000*0.11))
    
    assert adaptervault.convertToShares(2000) == 1058 # 1000    

    max_withdrawl = adaptervault.maxWithdraw(trader, sender=trader)
    max_redeem = adaptervault.maxRedeem(trader, sender=trader)

    shares_to_redeem = adaptervault.convertToShares(max_withdrawl)
    value_of_shares = adaptervault.convertToAssets(shares_to_redeem)
    print("max_withdrawl = %s." % max_withdrawl)
    print("max_redeem = %s." % max_redeem)
    print("shares_to_redeem = %s." % shares_to_redeem)
    print("value_of_shares = %s." % value_of_shares)

    assert max_withdrawl == 1000 + (1000 - (1000*0.11))
    assert max_redeem == 1000

    print("Got here #1.")

    # Setup current state of vault & adapters & strategy.
    cd4626_assets, cadapter_states, ctotal_assets, ctotal_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    adapters = adaptervault.getBalanceTxs(max_withdrawl, 5, 0, ctotal_assets, ctotal_ratios, cadapter_states, sender=trader)   

    print("adapters = %s." % [x for x in adapters])

    print("dai.balance_of(adapter_adapterA) = %s." % dai.balanceOf(adapter_adapterA))
    print("adaptervault.balance_of(trader) = %s." % adaptervault.balanceOf(trader))    

    #adaptervault.balanceAdapters(1889, sender=trader)


    print("Got here #2.")

    taken = adaptervault.withdraw(1890, trader, trader, 1890,sender=trader) 
    #taken = adaptervault.withdraw(1000, trader, trader, sender=trader) 
    print("Got back: %s shares, was expecting %s." % (taken.return_value, max_redeem))

    max_withdrawl = adaptervault.maxWithdraw(trader)
    max_redeem = adaptervault.maxRedeem(trader)

    assert max_withdrawl == pytest.approx(0), "Still got %s assets left to withdraw!" % max_withdrawl
    assert max_redeem == pytest.approx(0), "Still got %s shares left to redeem!" % max_redeem


def test_single_adapter_brakes_target_balance_txs(project, deployer, adaptervault, adapter_adapterA, adapter_adapterB, adapter_adapterC, dai, trader):
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterA)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,1000, sender=trader)

    result = adaptervault.deposit(1000, trader, sender=trader)
    
    d4626_assets, adapter_states, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    first_adapter = adapter_states[0]
    assert first_adapter.adapter == adapter_adapterA
    assert first_adapter.current == 1000
    assert first_adapter.last_value == 1000
    assert first_adapter.ratio == 1
    assert first_adapter.target == 0
    assert first_adapter.delta == 0
    assert total_assets == 1000
    assert total_ratios == 1   

    # Ape needs this conversion.
    adapters = [copy.deepcopy(x) for x in adapter_states]

    # Pretend to add another 1000.
    # The target for the first adapter's value should be the full amount.
    
    next_assets, moved, tx_count, adapter_txs, blocked_adapters = adaptervault.getTargetBalances(0, 2000, 1, adapters, 0)    

    assert blocked_adapters[0] == ZERO_ADDRESS    

    first_adapter = adapter_txs[0]
    assert first_adapter.adapter == adapter_adapterA
    assert first_adapter.current == 1000
    assert first_adapter.last_value == 1000
    assert first_adapter.ratio == 1
    assert first_adapter.target == 2000
    assert first_adapter.delta == 1000

    # Adjust as if it happened.
    first_adapter.current = 2000
    first_adapter.last_value = 2000
    first_adapter.target = 0
    first_adapter.delta = 0
    adapters[0]=first_adapter

    # Knock the first adapter's current value down as if there was a loss of 400 in that LP.
    adapters[0].current = 1600

    # Pretend to add another 1000.
    # No tx should be generated for the adapter as the brakes are applied due to the loss.
    next_assets, moved, tx_count, adapter_txs, blocked_adapters = adaptervault.getTargetBalances(0, 2000, 1, adapters, 0)

    assert blocked_adapters[0] == adapter_adapterA    

    assert adapter_txs[0].adapter == ZERO_ADDRESS
    assert adapter_txs[0].current == 0
    assert adapter_txs[0].last_value == 0

    assert adapter_txs[0].ratio == 0    
    assert adapter_txs[0].target == 0
    assert adapter_txs[0].delta== 0

    # Pretend adapter_adapterA has been kicked out.
    adapters[0].ratio = 0

    # Pretend to add another adapter.
    adapters[1].adapter = adapter_adapterB
    adapters[1].current = 0
    adapters[1].last_value = 0
    adapters[1].max_deposit = 9999999
    adapters[1].max_withdrawl = -9999999
    adapters[1].ratio = 1
    adapters[1].target = 0
    adapters[1].delta = 0


    next_assets, moved, tx_count, adapter_txs, blocked_adapters = adaptervault.getTargetBalances(0, 2000, 1, adapters, 0)

    # All the funds should be moved into adapter_adapterB.

    assert adapter_txs[0].adapter == adapter_adapterA
    assert adapter_txs[0].current == 1600
    assert adapter_txs[0].last_value == 2000
    assert adapter_txs[0].ratio == 0    
    assert adapter_txs[0].target == 0
    assert adapter_txs[0].delta== -1600

    assert adapter_txs[1].adapter == adapter_adapterB
    assert adapter_txs[1].current == 0
    assert adapter_txs[1].last_value == 0
    assert adapter_txs[1].ratio == 1    
    assert adapter_txs[1].target == 2000
    assert adapter_txs[1].delta== 2000


def test_single_adapter_brakes(project, deployer, adaptervault, adapter_adapterA, adapter_adapterB, dai, trader):
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterA)

    #pytest.skip("Not yet.")

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(adaptervault,5000, sender=trader)

    result = adaptervault.deposit(1000, trader, sender=trader)
    
    d4626_assets, adapter_states, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    assert adapter_states[0].adapter == adapter_adapterA
    assert adapter_states[0].current == 1000
    assert adapter_states[0].last_value == 1000
    assert adapter_states[0].ratio == 1 
    assert adapter_states[0].target == 0
    assert adapter_states[0].delta== 0
    assert total_assets == 1000
    assert total_ratios == 1   

    # Ape needs this conversion.
    adapters = [x for x in adapter_states]

    # Steal some funds from the Adapter.
    dai.transfer(deployer, 600, sender=adapter_adapterA)
    
    result = adaptervault.deposit(1000, trader, sender=trader)
    
    d4626_assets, adapter_states, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 1000
    assert adapter_states[0].adapter == adapter_adapterA    
    assert adapter_states[0].current == 400
    assert adapter_states[0].last_value == 1000    
    assert adapter_states[0].ratio == 0 # Now has been blocked! 
    assert adapter_states[0].target == 0
    assert adapter_states[0].delta== 0
    assert total_assets == 1400
    assert total_ratios == 0  

    # Add another adapter.
    _setup_single_adapter(project,adaptervault, deployer, dai, adapter_adapterB)

    adaptervault.balanceAdapters(0, _max_txs = MAX_ADAPTERS, sender=deployer)

    d4626_assets, adapter_states, total_assets, total_ratios = adaptervault.getCurrentBalances(sender=trader).return_value

    assert d4626_assets == 0
    assert adapter_states[0].adapter == adapter_adapterA    
    assert adapter_states[0].current == 0
    assert adapter_states[0].last_value == 0
    assert adapter_states[0].ratio == 0 
    assert adapter_states[0].target == 0
    assert adapter_states[0].delta== 0

    assert adapter_states[1].adapter == adapter_adapterB
    assert adapter_states[1].current == 1400
    assert adapter_states[1].last_value == 1400
    assert adapter_states[1].ratio == 1 
    assert adapter_states[1].target == 0
    assert adapter_states[1].delta== 0
    assert total_assets == 1400
    assert total_ratios == 1 


@dataclass
class DTx:
    adapter: str = ZERO_ADDRESS
    delta: int = 0

def countif(l):
    return sum(1 for y in [x for x in l if x.delta!=0])


def test_insertion_sort():    

    transactions = [DTx(x[0],x[1]) for x in [('0x123',-5),('0x456',4),('0x876',-25),('0x543',15)]]

    ordered_txs = [DTx()] * MAX_ADAPTERS

    for next_tx in transactions:
        if next_tx.delta == 0: continue # No txs allowed that do nothing.
        for pos in range(MAX_ADAPTERS):
            if ordered_txs[pos].delta == 0: # Empty position, take it.
                ordered_txs[pos]=next_tx
                print("first ordered_txs = %s\n" % ordered_txs)
                break
            elif ordered_txs[pos].delta > next_tx.delta: # Move everything right and insert here.
                for npos in range(MAX_ADAPTERS):
                    next_pos = MAX_ADAPTERS - npos - 1
                    if ordered_txs[next_pos].delta == 0: continue
                    ordered_txs[next_pos+1] = ordered_txs[next_pos]
                    
                ordered_txs[pos]=next_tx
                print("ordered_txs = %s\n" % ordered_txs)
                break

    # test got them all
    assert countif(transactions) == countif(ordered_txs), "Didn't get all txs."

    # test sorted order
    print("\n\nordered_txs = %s" % ordered_txs)
    print("sorted(transactions) = %s" % sorted(transactions, key=lambda x: x.delta))
    assert all([x[0].delta == x[1].delta for x in zip(ordered_txs, sorted(transactions, key=lambda x: x.delta))])

