#pragma version 0.3.10
#pragma evm-version cancun

"""
@title Adapter Fund Allocation Logic
@license Copyright 2023, 2024 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Benjamin Scherrey

Slippage is an insidious little parasite because attempts to optimize funds into the best mix of
returns generally results in higher transaction quantities which gives more opportunity for the
parasites to bite us! This makes optimizations generally counter productive when applied across
multiple adapters inside a single transaction. This funds allocator model is designed to treat the
strategy model as more of a direction than a destination and gradually approach an optimum strategy
goals over multiple user transactions rather than each time.

Now, for any deposit, we will only interact with a single adapter - that being the one that is most
out of balance compared to the ideal distribution of funds according to the current active strategy
ratios. However, since deposits are possibly restricted due to Adapter.maxDeposit() limits, there
could be situations where the full amount of the deposit is not able to be deposited into the
targeted adapter. Should that happen, the default condition is the remaining funds will sit in the
4626 Vault buffer and be unallocated. This is not desirable because the next depositor will not
only be moving their funds into an adapter but also the left over funds as well which potentially
exposes the tx to additional slippage increasing the risk of their tx reverting due to slippage 
violations.

To counteract the above exception condition we are introducing a "neutral adapter". This is an
adapter that simply holds the assets and does nothing to swap them into any other asset. It just
holds them as a buffer and takes the place of the main 4626 vault buffer. This adapter can be
identified as the special "neutral adapter" because a call to it's Adapter.maxDesposit() function
will always return convert(max_value(int256) - 42), uint256) as a special indicator that this
adapter is not going to have any slippage or fees so is safe to hold "leftovers". All future
withdraws will always try to pull from the "neutral adapter" first. And even if the "neutral
adapter" has a 0 strategy ratio, leftovers will still get deposited there. If a "neutral adapter"
has not been deployed then the default original behavior of using the 4626 vault buffer will resume.

Finally - to support the 4626 vault's full balanceAdapters capabilities, we will check for some
indication (TBD) that will let us know the contract owner has directly invoked this thus producing
multiple txs to get the Vault fully aligned to the current strategy.
"""

##
## Must match AdapterVault.vy
##

MAX_ADAPTERS : constant(uint256) = 5 

ADAPTER_BREAKS_LOSS_POINT : constant(decimal) = 0.05

# This structure must match definition in AdapterVault.vy
struct BalanceTX:
    qty: int256
    adapter: address

# This structure must match definition in AdapterVault.vy
struct BalanceAdapter:
    adapter: address
    current: uint256
    last_value: uint256
    max_deposit: int256
    max_withdraw: int256 # represented as a negative number
    ratio: uint256
    target: uint256 
    delta: int256


@external
@view
def getBalanceTxs(_vault_balance: uint256, _target_asset_balance: uint256, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_states: BalanceAdapter[MAX_ADAPTERS], _withdraw_only : bool = False) -> (BalanceTX[MAX_ADAPTERS], address[MAX_ADAPTERS]):  
    return self._getBalanceTxs(_vault_balance, _target_asset_balance, _min_proposer_payout, _total_assets, _total_ratios, _adapter_states, _withdraw_only )


@internal
@pure
def _getBalanceTxs(_vault_balance: uint256, _target_asset_balance: uint256, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_states: BalanceAdapter[MAX_ADAPTERS], _withdraw_only : bool = False) -> (BalanceTX[MAX_ADAPTERS], address[MAX_ADAPTERS]): 
    # _BDM TODO : max_txs is ignored for now.    
    adapter_txs : BalanceTX[MAX_ADAPTERS] = empty(BalanceTX[MAX_ADAPTERS])
    blocked_adapters : address[MAX_ADAPTERS] = empty(address[MAX_ADAPTERS])
    adapter_states: BalanceAdapter[MAX_ADAPTERS] = empty(BalanceAdapter[MAX_ADAPTERS])
    d4626_delta : int256 = 0
    tx_count : uint256 = 0

    #d4626_delta, tx_count, adapter_states, blocked_adapters = self._getTargetBalances(_vault_balance, _target_asset_balance, _total_assets, _total_ratios, _adapter_states, _min_proposer_payout, _withdraw_only)

    pos : uint256 = 0
    for tx_bal in adapter_states:
        adapter_txs[pos] = BalanceTX({qty: tx_bal.delta, adapter: tx_bal.adapter})
        pos += 1

    return adapter_txs, blocked_adapters


@internal
@view
def _is_full_rebalance() -> bool:
    return False


NEUTRAL_ADAPTER_MAX_DEPOSIT : constant(int256) = max_value(int256) - 42


@internal
@pure
def _allocate_balance_adapter_tx(_ratio_value : uint256, _balance_adapter : BalanceAdapter) -> (BalanceAdapter, int256, bool, bool):
    """
    Given a value per strategy ratio and an un-allocated BalanceAdapter, return the newly allocated BalanceAdapter
    constrained by min & max limits and also identify if this adapter should be blocked due to unexpected losses,
    plus identify whether or not this is our "neutral adapter".
    """
    is_neutral_adapter : bool = _balance_adapter.max_deposit == NEUTRAL_ADAPTER_MAX_DEPOSIT

    # Have funds been lost?
    should_we_block_adapter : bool = False
    if _balance_adapter.current < _balance_adapter.last_value:
        # There's an unexpected loss of value. Let's try to empty this adapter and stop
        # further allocations to it by setting the ratio to 0 going forward.
        # This will not necessarily result in any "leftovers" unless withdrawing the full
        # balance of the adapter is limited by max_withdraw limits below.
        _balance_adapter.ratio = 0
        should_we_block_adapter = True

    target : uint256 = _ratio_value * _balance_adapter.ratio
    delta : int256 = convert(target, int256) - convert(_balance_adapter.current, int256) 

    leftovers : int256 = 0
    # Limit deposits to max_deposit
    if delta > _balance_adapter.max_deposit:
        leftovers = _balance_adapter.max_deposit - delta
        delta = _balance_adapter.max_deposit

    # Limit withdraws to max_withdraw    
    elif delta < _balance_adapter.max_withdraw:
        leftovers = delta - _balance_adapter.max_withdraw
        delta = _balance_adapter.max_withdraw

    _balance_adapter.delta = delta
    _balance_adapter.target = target  # We are not adjusting the optimium target for now.

    return _balance_adapter, leftovers, should_we_block_adapter, is_neutral_adapter


@external
@pure
def allocate_balance_adapter_tx(_ratio_value : uint256, _balance_adapter : BalanceAdapter) -> (BalanceAdapter, int256, bool, bool):
    return self._allocate_balance_adapter_tx(_ratio_value, _balance_adapter)

