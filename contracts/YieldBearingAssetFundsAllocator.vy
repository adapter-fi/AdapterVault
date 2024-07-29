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

# TODO : create a _generate_full_balance_txs function similar to _generate_balance_txs

@internal
@pure
def _generate_balance_txs(_vault_balance: uint256, _target_asset_balance: uint256, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_states: BalanceAdapter[MAX_ADAPTERS], _withdraw_only : bool) -> (BalanceTX[MAX_ADAPTERS], address[MAX_ADAPTERS]):     

    # TODO : take into account _min_proposer_payout for deposits.

    adapter_txs : DynArray[BalanceTX,MAX_ADAPTERS] = empty(DynArray[BalanceTX,MAX_ADAPTERS])
    blocked_adapters : DynArray[BalanceAdapter,MAX_ADAPTERS] = empty(DynArray[BalanceAdapter,MAX_ADAPTERS])

    # Offsets in _adapter_states for key adapters
    max_delta_deposit_pos : uint256 = MAX_ADAPTERS
    min_delta_withdraw_pos : uint256 = MAX_ADAPTERS
    neutral_adapter_pos : uint256 = MAX_ADAPTERS

    remaining_funds_to_allocate : uint256 = _total_assets - _target_asset_balance
    if _total_ratios == 0: _total_ratios = 1 # Prevent a potential divide by zero exception.
    ratio_value : uint256 = remaining_funds_to_allocate / _total_ratios

    for pos in range(MAX_ADAPTERS):
        if _adapter_states[pos].adapter == empty(address):
            break
        leftovers : int256 = 0
        blocked : bool = False        
        neutral : bool = False

        _adapter_states[pos], leftovers, blocked, neutral = self._allocate_balance_adapter_tx(ratio_value, _adapter_states[pos])

        # Is this a blocked adapter now?
        if blocked:
            assert _adapter_states[pos].delta <= 0, "Blocked adapter flaw trying to deposit!" # This can't happen.
            blocked_adapters.append(_adapter_states[pos])
            # TODO FUTURE - if we're doing a deposit now would be the time to re-calculate the remaining_funds_to_allocate 
            #               and ratio_value in order to immediately re-invest these liquidated funds into other adapters.

        # Is this a key adapter? If so it's not eligible to be max deposit or min withdraw adapter unless no other qualifies.
        if neutral:
            neutral_adapter_pos = pos
            # TODO : update existing allocation & deposit/withdraw accounting.
        
        # Is this a deposit?
        elif _adapter_states[pos].delta > 0:
            # TODO: update existing allocation & deposit accounting.

            # Is this the largest deposit adapter out of balance?    
            if not blocked and ((max_delta_deposit_pos == MAX_ADAPTERS) or (_adapter_states[pos].delta > _adapter_states[max_delta_deposit_pos].delta)):
                max_delta_deposit_pos = pos

        # Is this a withdraw?
        elif _adapter_states[pos].delta < 0:
            # TODO: update existing allocation & withdraw accounting.

            # Is this the largest withdraw adapter out of balance?
            if not blocked and ((min_delta_withdraw_pos == MAX_ADAPTERS) or (_adapter_states[pos].delta < _adapter_states[min_delta_withdraw_pos].delta)):
                min_delta_withdraw_pos = pos

        # Otherwise there's no tx for this adapter.
        else:
            # TODO: update existing allocation accounting for no transfer.
            pass

    # Are we dealing with a deposit?
    if _target_asset_balance == 0 and _vault_balance > 0:

        # Do we have a best case adapter to receive the funds?
        if max_delta_deposit_pos != MAX_ADAPTERS:  

            # Do we need to redirect an overage?
            if _adapter_states[max_delta_deposit_pos].max_deposit < convert(_vault_balance, int256):
                _adapter_states[max_delta_deposit_pos].delta = _adapter_states[max_delta_deposit_pos].max_deposit
                adapter_txs.append( BalanceTX({qty: _adapter_states[max_delta_deposit_pos].max_deposit, 
                                               adapter: _adapter_states[max_delta_deposit_pos].adapter}) )                 

                # # Do we have a neutral adapter to take the rest?
                if neutral_adapter_pos != MAX_ADAPTERS:
                    adapter_txs.append( BalanceTX({qty: convert(_vault_balance, int256) - _adapter_states[max_delta_deposit_pos].max_deposit, 
                                                   adapter: _adapter_states[neutral_adapter_pos].adapter}) )

            # Great - it can take the whole thing.
            else:
                adapter_txs.append( BalanceTX({qty: convert(_vault_balance, int256), 
                                               adapter: _adapter_states[max_delta_deposit_pos].adapter}) ) 

        # No normal adapters available to take our deposit.
        else:
            # Do we have a neutral adapter to take the rest?
            if neutral_adapter_pos != MAX_ADAPTERS:
                assert convert(_vault_balance, int256) <= _adapter_states[neutral_adapter_pos].max_deposit, "Over deposit on neutral vault!"
                adapter_txs.append( BalanceTX({qty: convert(_vault_balance, int256), 
                                               adapter: _adapter_states[neutral_adapter_pos].adapter}) )
            # Nothing to do but let it sit in the vault buffer.
            else:
                pass


    # Is it a withdraw and is our buffer short of funds?
    elif _target_asset_balance > 0 and _vault_balance < _target_asset_balance:

        shortfall : uint256 = _target_asset_balance - _vault_balance

        # If there's some blocked adapters that we're recovering funds from, let's count them against
        # the shortfall now.
        for adapter in blocked_adapters:
            if convert(shortfall, int256) + adapter.delta <= 0:
                shortfall = 0
                break
            else:
                shortfall = convert(convert(shortfall,int256)+adapter.delta, uint256)

        # Always try to extract funds from the neutral adapter if possible.
        if neutral_adapter_pos != MAX_ADAPTERS and _adapter_states[neutral_adapter_pos].current > 0:
            if _adapter_states[neutral_adapter_pos].current > shortfall:
                # Got it all!
                adapter_txs.append( BalanceTX({qty: convert(shortfall, int256) * -1, 
                                               adapter: _adapter_states[neutral_adapter_pos].adapter}) )
                shortfall = 0
            else:
                # Got some...
                shortfall -= _adapter_states[neutral_adapter_pos].current
                adapter_txs.append( BalanceTX({qty: convert(_adapter_states[neutral_adapter_pos].current, int256) * -1, 
                                               adapter: _adapter_states[neutral_adapter_pos].adapter}) )

        # Is there still more to go and we have an adapter that most needs to remove funds?
        if shortfall > 0 and min_delta_withdraw_pos != MAX_ADAPTERS:
            if _adapter_states[min_delta_withdraw_pos].current > shortfall:
                # Got it all!
                shortfall = 0
                adapter_txs.append( BalanceTX({qty: convert(shortfall, int256) * -1, 
                                               adapter: _adapter_states[min_delta_withdraw_pos].adapter}) )
            else:
                # Got some...
                shortfall -= _adapter_states[min_delta_withdraw_pos].current
                adapter_txs.append( BalanceTX({qty: convert(_adapter_states[min_delta_withdraw_pos].current, int256) * -1, 
                                               adapter: _adapter_states[min_delta_withdraw_pos].adapter}) )

        # TODO - if we still have a shortfall then we have to walk across the remaining adapters (ignoring 
        #        min_delta_withdraw_pos & neutral_adapter_pos) until we come up with enough funds to fulfill the withdraw.
        if shortfall > 0:
            assert False, "HAPPY CASE NOT FOUND!"

    else:
        # This is withdraw satisfied by the vault buffer.
        pass

    result_txs : BalanceTX[MAX_ADAPTERS] = empty(BalanceTX[MAX_ADAPTERS])
    result_blocked : address[MAX_ADAPTERS] = empty(address[MAX_ADAPTERS])

    tx_pos : uint256 = 0
    tx_blocked : uint256 = 0
    for rtx in blocked_adapters:
        assert tx_pos < MAX_ADAPTERS, "Too many transactions #1!"
        result_txs[tx_pos] = BalanceTX({qty: rtx.delta, adapter: rtx.adapter})
        result_blocked[tx_blocked] = rtx.adapter
        tx_pos += 1
        tx_blocked += 1

    for rtx in adapter_txs:
        assert tx_pos < MAX_ADAPTERS, "Too many transactions #2!"
        result_txs[tx_pos] = rtx
        tx_pos += 1

    return result_txs, result_blocked


@external
@pure
def generate_balance_txs(_vault_balance: uint256, _target_asset_balance: uint256, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_states: BalanceAdapter[MAX_ADAPTERS], _withdraw_only : bool) -> (BalanceTX[MAX_ADAPTERS], address[MAX_ADAPTERS]):     
    """
    """
    return self._generate_balance_txs(_vault_balance, _target_asset_balance, _min_proposer_payout, _total_assets, _total_ratios, _adapter_states, _withdraw_only)
 

NEUTRAL_ADAPTER_MAX_DEPOSIT : constant(int256) = max_value(int256) - 42


@internal
@pure
def _allocate_balance_adapter_tx(_ratio_value : uint256, _balance_adapter : BalanceAdapter) -> (BalanceAdapter, int256, bool, bool):
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
        leftovers = delta - _balance_adapter.max_deposit
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
    """
    Given a value per strategy ratio and an un-allocated BalanceAdapter, return the newly allocated BalanceAdapter
    constrained by min & max limits and also identify if this adapter should be blocked due to unexpected losses,
    plus identify whether or not this is our "neutral adapter".
    """    
    return self._allocate_balance_adapter_tx(_ratio_value, _balance_adapter)

