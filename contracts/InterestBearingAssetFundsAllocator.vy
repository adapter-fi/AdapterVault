#pragma version 0.3.10
#pragma evm-version cancun
"""
@title Adapter Fund Allocation Logic
@license Copyright 2023, 2024 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Benjamin Scherrey
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


    