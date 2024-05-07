#pragma version 0.3.10
#pragma optimize codesize
"""
@title Adapter.FI Multi-Vault
@license Copyright 2023, 2024 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Benjamin Scherrey, Sajal Kayan
"""

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626
from adapters.IAdapter import IAdapter as IAdapter
implements: ERC20
# BDM HACK! We have some additional optional parameters that it doesn't like.
# implements: ERC4626

interface FundsAllocator:
    def getTargetBalances(_vault_balance: uint256, _d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_balances: BalanceAdapter[MAX_ADAPTERS], _min_outgoing_tx: uint256, _withdraw_only: bool) -> (uint256, int256, uint256, BalanceAdapter[MAX_ADAPTERS], address[MAX_ADAPTERS]): pure
    def getBalanceTxs(_vault_balance: uint256, _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_states: BalanceAdapter[MAX_ADAPTERS], _withdraw_only: bool) -> (BalanceTX[MAX_ADAPTERS], address[MAX_ADAPTERS]): pure

# Number of potential lenging platform adapters.
MAX_ADAPTERS : constant(uint256) = 5
MAX_BALTX_DEPOSIT : constant(uint8) = 5 # MUST equal MAX_ADAPTERS for now. Ignored for now.

MAX_SLIPPAGE_PERCENT : immutable(decimal)

# Contract owner hold 10% of the yield.
YIELD_FEE_PERCENTAGE : constant(uint256) = 10

# 1% of the yield belongs to the Strategy proposer.
PROPOSER_FEE_PERCENTAGE: constant(uint256) = 1

# For use in support of _claim_fees
enum FeeType:
    BOTH
    YIELDS
    PROPOSER

# ERC-20 attributes for this Vault's share token.
name: public(immutable(String[64]))
symbol: public(immutable(String[32]))
decimals: public(immutable(uint8))
asset: public(immutable(address))

# Controlling & Governance DAOs/Wallets
owner: public(address)
governance: public(address)
funds_allocator: public(address)
adapters : public(DynArray[address, MAX_ADAPTERS])

vault_asset_balance_cache: transient(uint256)
adapters_asset_balance_cache: transient(HashMap[address, uint256])
total_asset_balance_cache: transient(uint256)

# Strategy Management
current_proposer: public(address)
min_proposer_payout: public(uint256)

struct AdapterValue:
    ratio: uint256
    last_asset_value: uint256

strategy: public(HashMap[address, AdapterValue])


# Summary Financial History of the Vault
total_assets_deposited: public(uint256)
total_assets_withdrawn: public(uint256)
total_yield_fees_claimed: public(uint256)
total_strategy_fees_claimed: public(uint256)


# ERC20 Representation of Vault Shares
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])


event AdapterAdded:
    sender: indexed(address)
    adapter_addr: indexed(address)

event AdapterRemoved:   
    sender: indexed(address)
    afapter_addr: indexed(address)
    final_balance: uint256
    forced: bool  

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256    

event Deposit:
    sender: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256 

event SlippageDeposit:
    sender: indexed(address)
    owner: indexed(address)
    assets: uint256
    desired_shares: uint256     
    actual_shares: uint256

event Withdraw:
    sender: indexed(address)
    receiver: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256

event SlippageWithdraw:
    sender: indexed(address)
    receiver: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256    
    actual_assets : uint256

struct AdapterStrategy:
    adapter: address
    ratio: uint256    

event StrategyActivation:
    strategy: AdapterStrategy[MAX_ADAPTERS]
    proposer: address

event AdapterLoss:
    adapter: indexed(address)
    last_value: uint256
    current_value: uint256

event GovernanceChanged:
    new_governor: indexed(address)
    old_governor: indexed(address)

event VaultDeployed:
    name: indexed(String[64])
    symbol: indexed(String[32])
    decimals: uint8
    asset: indexed(address)

event FundsAllocatorChanged:
    new_allocator: indexed(address)
    old_allocator: indexed(address)   

event OwnerChanged:
    new_owner: indexed(address)
    old_owner: indexed(address)    


@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _erc20asset : address, _adapters: DynArray[address, MAX_ADAPTERS], _governance: address, _funds_allocator: address, _max_slippage_percent: decimal):
    """
    @notice Constructor for 4626 contract.
    @param _name of shares token
    @param _symbol identifier of shares token
    @param _decimals increment for division of shares token 
    @param _erc20asset : contract address for asset ERC20 token
    @param _adapters : list of addresses for initial Adapters (could be none) 
    @param _governance contract address
    @param _funds_allocator contract address
    @param _max_slippage_percent default maximum acceptable slippage for deposits/withdraws as a percentage
    """
    assert MAX_BALTX_DEPOSIT <= MAX_ADAPTERS, "Invalid contract pre-conditions."
    assert _governance != empty(address), "Governance cannot be null address."
    assert _funds_allocator != empty(address), "Fund allocator cannot be null address."
    MAX_SLIPPAGE_PERCENT = _max_slippage_percent

    name = _name
    symbol = _symbol
    decimals = _decimals

    # Is this likely to be an actual ERC20 contract?
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = empty(bool)
    result_ok, response = raw_call(_erc20asset, _abi_encode(self, method_id=method_id("balanceOf(address)")), max_outsize=32, value=convert(self, uint256), is_static_call=True, revert_on_failure=False)
    assert result_ok == True, "Doesn't appear to be an ERC20 contract."
    asset = _erc20asset

    self.owner = msg.sender
    self.governance = _governance
    self.funds_allocator = _funds_allocator
    self.totalSupply = 0

    log VaultDeployed(_name, _symbol, _decimals, _erc20asset)
    log OwnerChanged(msg.sender, empty(address))
    log GovernanceChanged(_governance, empty(address))
    log FundsAllocatorChanged(_funds_allocator, empty(address))

    for adapter in _adapters:
        self._add_adapter(adapter)        


@external
def replaceOwner(_new_owner: address) -> bool:
    """
    @notice replace the current 4626 owner with a new one.
    @param _new_owner address of the new contract owner
    @return True, if contract owner was replaced, False otherwise
    """
    assert msg.sender == self.owner, "Only existing owner can replace the owner."
    assert _new_owner != empty(address), "Owner cannot be null address."

    log OwnerChanged(_new_owner, self.owner)

    self.owner = _new_owner
    
    return True


@external
def replaceGovernanceContract(_new_governance: address) -> bool:
    """
    @notice replace the current Governance contract with a new one.
    @param _new_governance address of the new governance contract 
    @return True, if governance contract was replaced, False otherwise
    """
    assert msg.sender == self.governance, "Only existing Governance contract may replace itself."
    assert _new_governance != empty(address), "Governance cannot be null address."

    log GovernanceChanged(_new_governance, self.governance)

    self.governance = _new_governance    

    return True


@external
def replaceFundsAllocator(_new_funds_allocator: address) -> bool:
    """
    @notice replace the current funds allocator contract with a new one.
    @param _new_funds_allocator address of the new contract
    @return True, if funds allocator contract was replaced, False otherwise
    """
    assert msg.sender == self.owner, "Only owner can change the funds allocation contract!"
    assert _new_funds_allocator != empty(address), "FundsAllocator cannot be null address."

    log FundsAllocatorChanged(_new_funds_allocator, self.funds_allocator)

    self.funds_allocator = _new_funds_allocator

    return True


# Can't simply have a public adapters variable due to this Vyper issue:
# https://github.com/vyperlang/vyper/issues/2897
@view
@external
def adapter_list() -> DynArray[address, MAX_ADAPTERS]: 
    """
    @notice convenience function returning list of adapters
    @return list of lending adapter addresses
    """
    return self.adapters


@internal
def _set_strategy(_proposer: address, _strategies : AdapterStrategy[MAX_ADAPTERS], _min_proposer_payout : uint256, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]) -> bool:
    assert msg.sender == self.governance, "Only Governance DAO may set a new strategy."
    assert _proposer != empty(address), "Proposer can't be null address."

    # Are we replacing the old proposer?
    if self.current_proposer != _proposer:

        current_assets : uint256 = self._totalAssetsCached()

        # Is there enough payout to actually do a transaction?
        if self._claimable_fees_available(FeeType.PROPOSER, current_assets) > self.min_proposer_payout:
                
            # Pay prior proposer his earned fees.
            self._claim_fees(FeeType.PROPOSER, 0, pregen_info, current_assets)

        self.current_proposer = _proposer
        self.min_proposer_payout = _min_proposer_payout

    # Clear out all existing ratio allocations.
    for adapter in self.adapters:
        self.strategy[adapter] = empty(AdapterValue)

    # Now set strategies according to the new plan.
    for strategy in _strategies:
        plan : AdapterValue = empty(AdapterValue)
        plan.ratio = strategy.ratio
        self.strategy[strategy.adapter] = plan

    log StrategyActivation(_strategies, _proposer)

    return True


@external
def set_strategy(_proposer: address, _strategies : AdapterStrategy[MAX_ADAPTERS], _min_proposer_payout : uint256, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> bool:
    """
    @notice establishes new strategy of adapter ratios and minumum value of automatic txs into adapters
    @param _proposer address of wallet who proposed strategy and will be entitled to fees during its activation
    @param _strategies list of ratios for each adapter for funds allocation
    @param _min_proposer_payout for automated txs into adapters or automatic payout of fees to proposer upon activation of new strategy
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return True if strategy was activated, False overwise
    """
    return self._set_strategy(_proposer, _strategies, _min_proposer_payout, pregen_info)


@internal 
def _add_adapter(_adapter: address) -> bool:    
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can add new Lending Adapters."

    # Do we already support this adapter?
    assert (_adapter in self.adapters) == False, "adapter already supported."

    # Is this likely to be an actual IAdapter contract?
    # BDM - for some reason this raw_call blows up the contract size!
    #response: Bytes[32] = empty(Bytes[32])
    #result_ok: bool = empty(bool)

    #result_ok, response = raw_call(_adapter, method_id("maxDeposit()"), max_outsize=32, is_static_call=True, revert_on_failure=False)
    #assert (response != empty(Bytes[32])), "Doesn't appear to be an IAdapter."

    self.adapters.append(_adapter)

    log AdapterAdded(msg.sender, _adapter)

    return True


@external 
def add_adapter(_adapter: address) -> bool: 
    """
    @notice adds a new Adapter adapter to the 4626 vault.
    @param _adapter Address for new adapter to evaluate
    @return True if adapter was added, False otherwise
    @dev If the current strategy doesn't already have an allocation ratio for this adapter it will receive no funds until a new strategy is activated and a balanceAdapters or deposit/withdraw tx is made.

    """
    return self._add_adapter(_adapter)


@internal
@pure
def _defaultSlippage(_desiredAssets: uint256, _minAssets: uint256 = 0) -> uint256:
    min_transfer_balance : uint256 = _minAssets
    if _minAssets == 0:        
        min_transfer_balance = _desiredAssets - convert(convert(_desiredAssets, decimal) * (MAX_SLIPPAGE_PERCENT/100.0), uint256)
    assert _desiredAssets >= min_transfer_balance, "Desired assets cannot be less than minimum assets!"
    return min_transfer_balance


@internal
def _remove_adapter(_adapter: address, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS], _rebalance: bool = True, _force: bool = False, _min_assets: uint256 = 0) -> bool:
    # Is this from the owner?    
    assert msg.sender == self.owner, "Only owner can remove Lending Adapters."

    if _adapter not in self.adapters: return False

    # Determine acceptable slippage.
    adapter_assets : uint256 = self._adapterAssets(_adapter)
    min_transfer_balance : uint256 = self._defaultSlippage(adapter_assets, _min_assets)

    # Clear out any strategy ratio this adapter may have.
    self.strategy[_adapter].ratio = 0

    if _rebalance == True:
        initialVaultAssets : uint256 = self._totalAssetsCached()
        self._balanceAdapters(0, pregen_info, False, convert(MAX_ADAPTERS, uint8))
        if not _force:
            afterVaultAssets : uint256 = self._totalAssetsCached()
            if afterVaultAssets < initialVaultAssets:
                # We've taken some loss across the balancing transactions.
                loss : uint256 = initialVaultAssets - afterVaultAssets
                assert adapter_assets >= loss, "ERROR - loss was greater than adapter assets. Try to remove without rebalancing."
                assert min_transfer_balance >= adapter_assets - loss, "ERROR - too much slippage removing adapter. Try to remove without rebalancing."
    else:
        if adapter_assets > 0:
            assets_withdrawn : uint256 = self._adapter_withdraw(_adapter, adapter_assets, self, pregen_info, _force)
            if not _force:
                # If force semantics was chosen it means the contract owner is willing to leave any assets
                # behind in this adapter because it isn't behaving properly and we urgently need it gone.
                assert self._adapterAssets(_adapter) == 0, "ERROR - adapter adapter to be removed still has assets!"
                assert min_transfer_balance <= assets_withdrawn, "ERROR - too much slippage on adapter withdraw."

    # Walk over the list of adapters and get rid of this one.
    new_adapters : DynArray[address, MAX_ADAPTERS] = empty(DynArray[address, MAX_ADAPTERS])
    for adapter in self.adapters:
        if adapter != _adapter:
            new_adapters.append(adapter)

    self.adapters = new_adapters            

    log AdapterRemoved(msg.sender, _adapter, self._adapterAssets(_adapter), _force)

    return True


@external
def remove_adapter(_adapter: address, _rebalance: bool = True, _force: bool = False, _min_assets: uint256 = 0, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> bool:
    """
    @notice removes Adapter adapter from the 4626 vault.
    @param _adapter address to be removed 
    @param _rebalance if True will empty adapter before removal.
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return True if adapter was removed, False otherwise
    """
    return self._remove_adapter(_adapter, pregen_info, _rebalance, _force, _min_assets)


@internal
def _swap_adapters(_adapterOld: address, _adapterNew: address, _force: bool = False, _min_assets : uint256 = 0) -> bool:
    # Is this from the owner?    
    assert msg.sender == self.owner, "Only owner can swap Lending Adapters."
    assert _adapterOld != empty(address) and _adapterNew != empty(address), "Can't have empty address for adapter."

    OldAssets : uint256 = self._adapterAssets(_adapterOld)
    NewAssets : uint256 = self._adapterAssets(_adapterNew)

    if not _force and OldAssets > 0:
        # Is there any slippage?
        if NewAssets < OldAssets:
            min_transfer_balance : uint256 = self._defaultSlippage(OldAssets, _min_assets)
            # min_transfer_balance : uint256 = OldAssets

            # # If _min_assets isn't specified we based allowed slippage as a percentage.
            # if _min_assets == 0:
            #     slippage_allowed : uint256 = convert(convert(min_transfer_balance, decimal) * (MAX_SLIPPAGE_PERCENT/100.0), uint256)
            #     min_transfer_balance = min_transfer_balance - slippage_allowed

            assert min_transfer_balance <= NewAssets, "ERROR - Swap exceeds maximum slippage."

    # Now find the old adapter and replace with the new one.
    pos: uint256 = 0
    found : bool = False
    for adapter in self.adapters:
        if adapter == _adapterOld:
            found = True
            break
        pos += 1

    assert found, "Adapter to be replaced was not found."
    self.adapters[pos] = _adapterNew
    self.strategy[_adapterNew].ratio = self.strategy[_adapterOld].ratio
    self.strategy[_adapterNew].last_asset_value = NewAssets
    self.strategy[_adapterOld] = empty(AdapterValue)

    log AdapterRemoved(msg.sender, _adapterOld, self._adapterAssets(_adapterOld), _force)
    log AdapterAdded(msg.sender, _adapterNew)

    return True


@external
def swap_adapters(_adapterOld: address, _adapterNew: address, _force: bool = False, _min_assets : uint256 = 0) -> bool:
    """
    @notice changes swaps address for a adapter. This is the upgrade mechanism for an adapter.
    @param _adapterOld Address of the current adapter contract
    @param _adapterNew Address of the replacement adapter contract
    @param _force if True then complete the swap regardless of slippage.
    @param _min_assets the minimum amount of assets the replaement contract should report
    """
    return self._swap_adapters(_adapterOld, _adapterNew, _force, _min_assets)


@internal 
def _dirtyAssetCache(_clearVaultBalance : bool = True, _clearAdapters : bool = True, _adapter : address = empty(address)):
    self.total_asset_balance_cache = 0
    if _clearVaultBalance:
        self.vault_asset_balance_cache = 0 
    if _clearAdapters:        
        if _adapter == empty(address):
            # Clear them all
            for cache in range(0, MAX_ADAPTERS):
                self.adapters_asset_balance_cache[self.adapters[cache]] = 0
        else:
            self.adapters_asset_balance_cache[_adapter] = 0


@internal
def _vaultAssets() -> uint256:
    if self.vault_asset_balance_cache == 0:
        self.vault_asset_balance_cache = ERC20(asset).balanceOf(self)
    return self.vault_asset_balance_cache


@internal
def _adapterAssets(_adapter: address) -> uint256:
    if _adapter == empty(address):
        return 0

    result : uint256 = self.adapters_asset_balance_cache[_adapter]
    if result != 0:
        return result

    result = IAdapter(_adapter).totalAssets()
    self.adapters_asset_balance_cache[_adapter] = result
    return result


@internal
def _totalAssetsCached() -> uint256:
    assetqty : uint256 = self._vaultAssets()
    for adapter in self.adapters:
        assetqty += self._adapterAssets(adapter)

    return assetqty


@external
def try_total_assets() -> uint256:
    return self._totalAssetsCached()


@internal
@view 
def _totalAssetsNoCache() -> uint256:
    assetqty : uint256 = ERC20(asset).balanceOf(self)
    for adapter in self.adapters:
        assetqty += IAdapter(adapter).totalAssets()

    return assetqty


@external
@view
def totalAssets() -> uint256: 
    """
    @notice returns current total asset value for 4626 vault & all its attached Adapter adapters.
    @return sum of assets
    """
    return self._totalAssetsNoCache()
    


@internal
@view 
def _totalReturns(_current_assets : uint256) -> int256:
    # Avoid having to call _totalAssets if we already know the value.
    current_holdings : uint256 = _current_assets
    if current_holdings == 0:
        current_holdings = self._totalAssetsNoCache()

    total_returns: int256 = convert(self.total_assets_withdrawn + \
                                    current_holdings + \
                                    self.total_yield_fees_claimed + \
                                    self.total_strategy_fees_claimed, int256) - \
                            convert(self.total_assets_deposited, int256)
    return total_returns    


@external
@view 
def totalReturns() -> int256:
    """
    @notice computes current profits (denominated in assets) available under control of this 4626 vault.
    @return total assets held by adapter above what is currently deposited.
    @dev This includes the fees owed to 4626 contract owner and current strategy proposer.
    """
    assets : uint256 = self._totalAssetsNoCache()
    return self._totalReturns(assets)    


@internal
@view 
def _claimable_fees_available(_yield : FeeType, _current_assets : uint256 = 0) -> uint256:
    total_assets : uint256 = _current_assets

    # Only call _totalAssets() if it wasn't passed in.
    if total_assets == 0:
        total_assets = self._totalAssetsNoCache()

    total_returns : int256 = self._totalReturns(total_assets)
    if total_returns <= 0: 
        return 0

    total_yield_ever : uint256 = (convert(total_returns,uint256) * YIELD_FEE_PERCENTAGE) / 100
    total_strat_fees_ever : uint256 = (convert(total_returns,uint256) * PROPOSER_FEE_PERCENTAGE) / 100

    if _yield == FeeType.PROPOSER and \
        self.total_strategy_fees_claimed >= total_strat_fees_ever: 
            return 0
    elif _yield == FeeType.YIELDS and \
        self.total_yield_fees_claimed >= total_yield_ever:
            return 0
    elif _yield == FeeType.BOTH and \
        self.total_strategy_fees_claimed + self.total_yield_fees_claimed >= total_strat_fees_ever + total_yield_ever:
            return 0

    total_fees_available : uint256 = 0
    if _yield == FeeType.YIELDS or _yield == FeeType.BOTH:
        total_fees_available += total_yield_ever - self.total_yield_fees_claimed
    
    if _yield == FeeType.PROPOSER or _yield == FeeType.BOTH:
        total_fees_available += total_strat_fees_ever - self.total_strategy_fees_claimed           

    # We want to do the above sanity checks even if total_assets is zero just in case.
    #if total_assets == 0: return 0
    if total_assets < total_fees_available:
        # Is it a rounding error?
        if total_fees_available - 1 == total_assets:
            total_fees_available -= 1
        else:
            xxmsg : String[277] = concat("Fees ", uint2str(total_fees_available), " > current assets : ", uint2str(total_assets), " against ", uint2str(convert(total_returns,uint256)), " returns!")
            assert total_assets >= total_fees_available, xxmsg       

    return total_fees_available


@external
@view    
def claimable_yield_fees_available(_current_assets : uint256 = 0) -> uint256:
    """
    @notice determines total yields aailable for 4626 vault owner.
    @param _current_assets optional parameter if current total assets is already known.
    @return total assets contract owner could withdraw now in fees.
    """
    return self._claimable_fees_available(FeeType.YIELDS, _current_assets)    


@external
@view    
def claimable_strategy_fees_available(_current_assets : uint256 = 0) -> uint256:
    """
    @notice determines total yields aailable for current strategy proposer.
    @param _current_assets optional parameter if current total assets is already known.
    @return total assets strategy proposer is owed presently.
    """
    return self._claimable_fees_available(FeeType.PROPOSER, _current_assets)  


@external
@view    
def claimable_all_fees_available(_current_assets : uint256 = 0) -> uint256:
    """
    @notice determines total fees owed for both 4626 vault owner & proposer of current strategy.
    @param _current_assets optional parameter if current total assets is already known.
    @return Claimable fees available for yield and proposer
    """
    return self._claimable_fees_available(FeeType.BOTH, _current_assets)      


@internal
def _claim_fees(_yield : FeeType, _asset_amount: uint256, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS], _current_assets : uint256 = 0) -> uint256:
    # If current proposer is zero address we pay no strategy fees.    
    if _yield != FeeType.YIELDS and self.current_proposer == empty(address): return 0

    claim_amount : uint256 = _asset_amount

    total_fees_remaining : uint256 = self._claimable_fees_available(_yield, _current_assets)
    if _asset_amount == 0:
        claim_amount = total_fees_remaining

    # Do we have _asset_amount of fees available to claim?
    assert claim_amount <= total_fees_remaining, "Request exceeds available fees."

    # Good claim. Do we have the balance locally?
    if ERC20(asset).balanceOf(self) < claim_amount:

        # Need to liquidate some shares to fulfill 
        self._balanceAdapters(claim_amount, pregen_info)

    strat_fee_amount : uint256 = 0
    if _yield == FeeType.PROPOSER or _yield == FeeType.BOTH: 
        assert msg.sender == self.current_proposer or msg.sender == self.governance, "Only curent proposer or governance may claim strategy fees."

        strat_fee_amount = min(claim_amount, self._claimable_fees_available(FeeType.PROPOSER, _current_assets))
        claim_amount -= strat_fee_amount

    elif _yield == FeeType.YIELDS:
        assert msg.sender == self.owner, "Only owner may claim yield fees."

    else:
        assert False, "Invalid FeeType!"    

    self.total_yield_fees_claimed += claim_amount
    self.total_strategy_fees_claimed += strat_fee_amount

    # Do we have something independent for the strategy proposer?
    if strat_fee_amount > 0 and self.owner != self.current_proposer:
        ERC20(asset).transfer(self.current_proposer, strat_fee_amount)
        
    # Is there anything left over to transfer for Yield? (Which might also include strat)
    if claim_amount > 0:
        ERC20(asset).transfer(self.owner, claim_amount + strat_fee_amount)    

    # Clear vault asset cache!
    if strat_fee_amount > 0 or claim_amount > 0:               
        self._dirtyAssetCache(True, False)        

    return claim_amount + strat_fee_amount


@external
def claim_yield_fees(_asset_request: uint256 = 0, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> uint256:
    """
    @notice used by 4626 vault owner to withdraw fees.
    @param _asset_request total assets desired for withdrawl. 
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return total assets transferred.    
    @dev If _asset_request is 0 then will withdrawl all eligible assets.
    """
    return self._claim_fees(FeeType.YIELDS, _asset_request, pregen_info)


@external
def claim_strategy_fees(_asset_request: uint256 = 0, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> uint256:
    """
    @notice user by current Strategy proposer to withdraw fees.
    @param _asset_request total assets desired for withdrawl. 
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return total assets transferred.    
    @dev If _asset_request is 0 then will withdrawl all eligible assets.
    """
    return self._claim_fees(FeeType.PROPOSER, _asset_request, pregen_info)


@external
def claim_all_fees(_asset_request: uint256 = 0, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> uint256:
    """
    @notice if 4626 vault owner and Strategy proposer are same wallet address, used to withdraw all fees at once.
    @param _asset_request total assets desired for withdrawl. 
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return total assets transferred.    
    @dev If _asset_request is 0 then will withdrawl all eligible assets.
    """
    return self._claim_fees(FeeType.BOTH, _asset_request, pregen_info)


@internal
@view
def _convertToShares(_asset_amount: uint256, _starting_assets: uint256) -> uint256:
    shareqty : uint256 = self.totalSupply
    claimable_fees : uint256 = self._claimable_fees_available(FeeType.BOTH, _starting_assets)
    
    # Less fees
    assert _starting_assets >= claimable_fees, "_convertToShares sanity failure!" # BDM
    assetqty : uint256 = _starting_assets - claimable_fees

    # If there aren't any shares/assets yet it's going to be 1:1.
    if shareqty == 0 : return _asset_amount
    if assetqty == 0 : return _asset_amount

    return _asset_amount * shareqty / assetqty 


@external
@view
def convertToShares(_asset_amount: uint256) -> uint256: 
    """
    @notice calculates the current number of 4626 shares would be received for a deposit of assets.
    @param _asset_amount the quantity of assets to be converted to shares.
    @return current share value for the asset quantity
    @dev any fees owed to 4626 owner or strategy proposer are removed before conversion.
    """
    return self._convertToShares(_asset_amount, self._totalAssetsNoCache())

@internal
@view
def _convertToAssets(_share_amount: uint256, _starting_assets: uint256) -> uint256:
    shareqty : uint256 = self.totalSupply
    claimable_fees : uint256 = self._claimable_fees_available(FeeType.BOTH, _starting_assets)
    
    # Less fees
    assert _starting_assets >= claimable_fees, "_convertToAssets sanity failure!" # BDM    

    # If there aren't any shares yet it's going to be 1:1.
    if shareqty == 0: return _share_amount    
    if _starting_assets - claimable_fees == 0 : return _share_amount    

    return _share_amount * (_starting_assets - claimable_fees) / shareqty


@external
@view
def convertToAssets(_share_amount: uint256) -> uint256:
    """
    @notice calculates the current quantity of assets would be received for a deposit of 4626 shares.
    @param _share_amount the quantity of 4626 shares to be converted to assets.
    @return current asset value for the share quantity
    @dev any fees owed to 4626 owner or strategy proposer are removed before conversion.
    """
    return self._convertToAssets(_share_amount, self._totalAssetsNoCache())


@external
@view
def maxDeposit(_spender: address) -> uint256:
    """
    @notice Maximum amount of the underlying asset that can be deposited into the Vault for the receiver, through a deposit call.
    @param _spender address (ignored)
    @return a really big number that we'll never hit.
    @dev Due to the nature of the LPs that we depend upon there's no way to properly support this part of the EIP-4626 spec.
    """
    return convert(max_value(int128), uint256)


@external
@view
def previewDeposit(_asset_amount: uint256) -> uint256:
    """
    @notice This function converts asset amount to shares in deposit
    @param _asset_amount Number amount of assets to evaluate
    @return Shares per asset amount in deposit
    """
    return self._convertToShares(_asset_amount, self._totalAssetsNoCache())


@external
@view
def maxMint(_receiver: address) -> uint256:
    """
    @notice Maximum amount of shares that can be minted from the Vault for the receiver, through a mint call.
    @param _receiver address (ignored)
    @return a really big number that we'll never hit.
    @dev Due to the nature of the LPs that we depend upon there's no way to properly support this part of the EIP-4626 spec.
    """
    return convert(max_value(int128), uint256)


@external
@view 
def previewMint(_share_amount: uint256) -> uint256:
    """
    @notice This function returns asset qty that would be returned for this share_amount per mint
    @param _share_amount Number amount of shares to evaluate
    @return Assets per share amount in mint
    """
    return self._convertToAssets(_share_amount, self._totalAssetsNoCache())


@external
def mint(_share_amount: uint256, _receiver: address, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS] = empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> uint256:
    """
    @notice This function mints asset qty that would be returned for this share_amount to receiver
    @param _share_amount Number amount of shares to evaluate
    @param _receiver Address of receiver to evaluate
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return Asset value of _share_amount
    """
    assetqty : uint256 = self._convertToAssets(_share_amount, self._totalAssetsCached())
    return self._deposit(assetqty, _receiver, pregen_info)


@external
@view 
def maxWithdraw(_owner: address) -> uint256:
    """
    @notice This function returns maximum assets this _owner can extract
    @param _owner Address of owner of assets to evaluate
    @return maximum assets this _owner can withdraw
    """
    return self._convertToAssets(self.balanceOf[_owner], self._totalAssetsNoCache())


@external
@view 
def previewWithdraw(_asset_amount: uint256) -> uint256:
    """
    @notice This function returns asset qty per share amount for withdraw
    @param _asset_amount Number amount of assets to evaluate
    @return Share qty per asset amount in withdraw
    """
    return self._convertToShares(_asset_amount, self._totalAssetsNoCache())


@external
@view 
# Returns maximum shares this _owner can redeem.
def maxRedeem(_owner: address) -> uint256:
    """
    @notice This function returns maximum shares this _owner can redeem
    @param _owner Address of owner of assets to evaluate
    @return maximum shares this _owner can redeem
    """
    return self.balanceOf[_owner]


@external
@view 
def previewRedeem(_share_amount: uint256) -> uint256:
    """
    @notice This function returns asset qty per share amount for redemption
    @param _share_amount Number amount of shares to evaluate
    @return asset qty per share amount in redemption
    """
    return self._convertToAssets(_share_amount, self._totalAssetsNoCache())


@external
def redeem(_share_amount: uint256, _receiver: address, _owner: address, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> uint256:
    """
    @notice This function redeems asset qty that would be returned for this share_amount to receiver from owner
    @param _share_amount Number amount of shares to evaluate
    @param _receiver Address of receiver to evaluate
    @param _owner Address of owner of assets to evaluate
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return Asset qty withdrawn
    """
    assetqty: uint256 = self._convertToAssets(_share_amount, self._totalAssetsCached())
    # NOTE - this is accepting the MAX_SLIPPAGE_PERCENT % slippage default.
    return self._withdraw(assetqty, _receiver, _owner, pregen_info, 0)


# This structure must match definition in Funds Allocator contract.
struct BalanceTX:
    qty: int256
    adapter: address

# This structure must match definition in Funds Allocator contract.
struct BalanceAdapter:
    adapter: address
    current: uint256
    last_value: uint256
    max_deposit: int256
    max_withdraw: int256 # represented as a negative number
    ratio: uint256
    target: uint256 
    delta: int256


@internal
@view
def _getAdapterMaxWithdraw(_adapter: address) -> int256:
    """
    @dev Given an adapter's address return the maximum withdraw 
    amount allowed for that adapter. 
    """
    # If the value is higher than what can be represented by an int256 
    # make it the maximum value possible with an int256.
    _umax : uint256 = IAdapter(_adapter).maxWithdraw()
    if _umax > convert(max_value(int256), uint256):
        _umax = convert(max_value(int256), uint256)

    return convert(_umax, int256) * -1        


@internal
@view
def _getAdapterMaxDeposit(_adapter: address) -> int256:
    """
    @dev Given an adapter's address return the maximum deposit 
    amount allowed for that adapter. This will be a negative number.
    """
    # If the value is higher than what can be represented by an int256 
    # make it the maximum value possible with an int256.
    _umax : uint256 = IAdapter(_adapter).maxDeposit()
    if _umax > convert(max_value(int256), uint256):
        return max_value(int256)

    return convert(_umax, int256)


# Returns current 4626 asset balance, first 3 parts of BalanceAdapters, total Assets, & total ratios of Strategy.
@internal
def _getCurrentBalances() -> (uint256, BalanceAdapter[MAX_ADAPTERS], uint256, uint256):
    current_local_asset_balance : uint256 = self._vaultAssets()

    adapter_balances: BalanceAdapter[MAX_ADAPTERS] = empty(BalanceAdapter[MAX_ADAPTERS])


    # If there are no adapters then nothing to do.
    if len(self.adapters) == 0: return current_local_asset_balance, adapter_balances, current_local_asset_balance, 0

    total_balance: uint256 = current_local_asset_balance
    total_ratios: uint256 = 0
    pos: uint256 = 0

    for adapter in self.adapters:
        adapter_balances[pos].adapter = adapter
        adapter_balances[pos].current = self._adapterAssets(adapter)
        total_balance += adapter_balances[pos].current

        adapter_balances[pos].max_withdraw = self._getAdapterMaxWithdraw(adapter)
        adapter_balances[pos].max_deposit = self._getAdapterMaxDeposit(adapter)

        plan : AdapterValue = self.strategy[adapter]

        adapter_balances[pos].ratio = plan.ratio

        total_ratios += plan.ratio
        adapter_balances[pos].last_value = plan.last_asset_value
        
        pos += 1

    return current_local_asset_balance, adapter_balances, total_balance, total_ratios


@external
def getCurrentBalances() -> (uint256, BalanceAdapter[MAX_ADAPTERS], uint256, uint256): 
    """
    @notice This function returns current balances of adapters
    @return Current balances of adapters
    """
    return self._getCurrentBalances()


@external
@view
def getTargetBalances(_d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_balances: BalanceAdapter[MAX_ADAPTERS], _min_outgoing_tx: uint256, _withdraw_only : bool = False) -> (uint256, int256, uint256, BalanceAdapter[MAX_ADAPTERS], address[MAX_ADAPTERS]): 
    """
    @dev    Returns: 
            1) uint256 - the total asset allocation across all adapters (less _d4626_asset_target),
            2) int256 - the total delta of local d4626 assets that would be moved across
            all transactions, 
            3) uint256 - the total number of planned txs to achieve these targets,
            4) BalanceAdapter[MAX_ADAPTERS] - the updated list of transactions required to
            meet the target goals sorted in ascending order of BalanceAdapter.delta.
            5) A list of any adapters that should be blocked because they lost funds.

    @param  _d4626_asset_target minimum asset target goal to be made available
            for withdraw from the 4626 contract.

    @param  _total_assets the sum of all assets held by the d4626 plus all of
            its adapter adapters.

    @param _total_ratios the total of all BalanceAdapter.ratio values in _adapter_balances.

    @param _adapter_balances current state of the adapter adapters. BDM TODO Specify TYPES!

    @param _min_outgoing_tx the minimum size of a tx depositing funds to an adapter (as set by the current strategy).

    """    
    current_local_asset_balance : uint256 = ERC20(asset).balanceOf(self)

    return FundsAllocator(self.funds_allocator).getTargetBalances(current_local_asset_balance, _d4626_asset_target, _total_assets, _total_ratios, _adapter_balances, _min_outgoing_tx, _withdraw_only)


@internal
@view
def _getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_states: BalanceAdapter[MAX_ADAPTERS], _withdraw_only : bool = False) -> (BalanceTX[MAX_ADAPTERS], address[MAX_ADAPTERS]): 
    current_local_asset_balance : uint256 = ERC20(asset).balanceOf(self)
    return FundsAllocator(self.funds_allocator).getBalanceTxs( current_local_asset_balance, _target_asset_balance, _max_txs, _min_proposer_payout, _total_assets, _total_ratios, _adapter_states, _withdraw_only)


@external
@view
def getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _adapter_states: BalanceAdapter[MAX_ADAPTERS], _withdraw_only : bool = False) -> (BalanceTX[MAX_ADAPTERS], address[MAX_ADAPTERS]):  
    current_local_asset_balance : uint256 = ERC20(asset).balanceOf(self)
    return FundsAllocator(self.funds_allocator).getBalanceTxs( current_local_asset_balance, _target_asset_balance, _max_txs, _min_proposer_payout, _total_assets, _total_ratios, _adapter_states, _withdraw_only)


@internal
def _balanceAdapters( _target_asset_balance: uint256, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS], _withdraw_only : bool = False, _max_txs: uint8 = MAX_BALTX_DEPOSIT ):
    # Make sure we have enough assets to send to _receiver.
    txs: BalanceTX[MAX_ADAPTERS] = empty(BalanceTX[MAX_ADAPTERS])
    blocked_adapters: address[MAX_ADAPTERS] = empty(address[MAX_ADAPTERS])

    # If there are no adapters then nothing to do.
    if len(self.adapters) == 0: return 

    # Setup current state of vault & adapters & strategy.
    d4626_assets: uint256 = 0
    adapter_states: BalanceAdapter[MAX_ADAPTERS] = empty(BalanceAdapter[MAX_ADAPTERS])
    total_assets: uint256 = 0
    total_ratios: uint256 = 0
    d4626_assets, adapter_states, total_assets, total_ratios = self._getCurrentBalances()

    txs, blocked_adapters = self._getBalanceTxs(_target_asset_balance, _max_txs, self.min_proposer_payout, total_assets, total_ratios, adapter_states )

    # If there are blocked_adapters then set their strategy ratios to zero.
    for adapter in blocked_adapters:
        if adapter == empty(address): break

        new_strat : AdapterValue = self.strategy[adapter]
        new_strat.ratio = 0
        self.strategy[adapter] = new_strat

        log AdapterLoss(adapter, new_strat.last_asset_value, self._adapterAssets(adapter))

    # Move the funds in/out of Lending Adapters as required.
    for dtx in txs:
        if dtx.adapter == empty(address): break
        if dtx.qty == 0: continue

        # If the outgoing tx is larger than the min_proposer_payout then do it, otherwise ignore it.
        if dtx.qty > 0 and dtx.qty >= convert(self.min_proposer_payout, int256):
            # Move funds into the lending adapter's adapter.

            # Account for the possibility that slippage occurred in a prior tx withdraw
            # from another adapter so it's possible the vault is a little short.
            tx_qty : uint256 = convert(dtx.qty, uint256)

            asset_amount : uint256 = ERC20(asset).balanceOf(self)
            if tx_qty > asset_amount:
                min_transfer_balance : uint256 = self._defaultSlippage(tx_qty, 0)

                if asset_amount >= min_transfer_balance:
                    tx_qty = asset_amount

            assert ERC20(asset).balanceOf(self) >= tx_qty, "_balanceAdapters d4626 insufficient assets!"
            self._adapter_deposit(dtx.adapter, tx_qty, pregen_info)

        elif dtx.qty < 0:
            # Liquidate funds from lending adapter's adapter.
            qty: uint256 = convert(dtx.qty * -1, uint256)         
            assets_withdrawn : uint256 = self._adapter_withdraw(dtx.adapter, qty, self, pregen_info)


@external
def balanceAdapters( _target_asset_balance: uint256, _withdraw_only : bool = False, _max_txs: uint8 = MAX_BALTX_DEPOSIT, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])):
    """
    @notice The function provides a way to balance adapters
    @param _target_asset_balance Target amount for assets balance
    @param _max_txs Maximum amount of adapters
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    """
    assert msg.sender == self.owner, "only owner can call balanceAdapters"
    self._balanceAdapters(_target_asset_balance, pregen_info, _withdraw_only, _max_txs)


@internal
def _mint(_receiver: address, _share_amount: uint256) -> uint256:
    """
    @dev Mint an amount of the token and assigns it to an account.
         This encapsulates the modification of balances such that the
         proper events are emitted.
    @param _to The account that will receive the created tokens.
    @param _value The amount that will be created.
    """
    assert _receiver != empty(address), "Receiver cannot be zero."
    self.totalSupply += _share_amount
    self.balanceOf[_receiver] += _share_amount
    log Transfer(empty(address), _receiver, _share_amount)
    return _share_amount


@internal
@view
def _extract_pregen_info(_pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS], _adapter: address) -> Bytes[4096]:
    #Only extract if pregeninfo len matches lending adapters
    if len(_pregen_info) == len(self.adapters):
        #find idx current adapter
        idx: uint256 = 0
        for adapter in self.adapters:
            if _adapter == adapter:
                return _pregen_info[idx]
            idx+=1
    return empty(Bytes[4096])


@internal
def _adapter_deposit(_adapter: address, _asset_amount: uint256, _pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]):
    pregen_info: Bytes[4096] = self._extract_pregen_info(_pregen_info, _adapter)
    response: Bytes[32] = empty(Bytes[32])

    starting_assets : uint256 = self._adapterAssets(_adapter)

    response = raw_call(
        _adapter,
        _abi_encode(_asset_amount, pregen_info, method_id=method_id("deposit(uint256,bytes)")),
        max_outsize=32,
        is_delegate_call=True,
        revert_on_failure=True
        )

    # Clear the asset cache for vault and adapter.
    self._dirtyAssetCache(True, True, _adapter)

    new_assets : uint256 = self._adapterAssets(_adapter)

    # Update our last_asset_value in our strategy for protection against LP exploits.
    self.strategy[_adapter].last_asset_value = new_assets


@internal
def _adapter_withdraw(_adapter: address, _asset_amount: uint256, _withdraw_to: address, _pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS], _force: bool = False) -> uint256:
    pregen_info: Bytes[4096] = self._extract_pregen_info(_pregen_info, _adapter)
    balbefore : uint256 = ERC20(asset).balanceOf(_withdraw_to)
    response: Bytes[32] = empty(Bytes[32])
    result_ok : bool = True

    assert _adapter != empty(address), "EMPTY ADAPTER!"
    assert _withdraw_to != empty(address), "EMPTY WITHDRAW_TO!"

    if _force:

        # For revery_on_failure = True
        result_ok, response = raw_call(
            _adapter,
            _abi_encode(_asset_amount, _withdraw_to, pregen_info, method_id=method_id("withdraw(uint256,address,bytes)")),
            max_outsize=32,
            is_delegate_call=True,
            revert_on_failure=False
            )
    else:
        # For revert_on_failure = False
        response = raw_call(
            _adapter,
            _abi_encode(_asset_amount, _withdraw_to, pregen_info, method_id=method_id("withdraw(uint256,address,bytes)")),
            max_outsize=32,
            is_delegate_call=True,
            revert_on_failure=True
            )

    # Clear the asset cache for vault and adapter.
    self._dirtyAssetCache(True, True, _adapter)                        

    balafter : uint256 = ERC20(asset).balanceOf(_withdraw_to)
    
    # Update our last_asset_value in our strategy for protection against LP exploits.
    self.strategy[_adapter].last_asset_value = self._adapterAssets(_adapter)

    return balafter - balbefore


@internal
def _deposit(_asset_amount: uint256, _receiver: address, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS], _min_shares : uint256 = 0) -> uint256:
    assert _receiver != empty(address), "Cannot send shares to zero address."

    assert _asset_amount <= ERC20(asset).balanceOf(msg.sender), "4626Deposit insufficient funds."

    total_starting_assets : uint256 = self._totalAssetsCached()

    # MUST COMPUTE IDEAL SHARES FIRST!
    ideal_shares : uint256 = self._convertToShares(_asset_amount, total_starting_assets)
    transfer_shares : uint256 = ideal_shares
    spot_share_price : decimal = convert(ideal_shares, decimal) / convert(_asset_amount, decimal)
    # We'd like to do it this way but if there's an overall loss we might not be able to complete deposits later.
    

    # Compute minimum acceptable shares
    min_transfer_shares : uint256 = self._defaultSlippage(transfer_shares, _min_shares)
    assert transfer_shares >= min_transfer_shares, "Desired assets cannot be less than minimum assets!"

    # Move assets to this contract from caller in one go.
    ERC20(asset).transferFrom(msg.sender, self, _asset_amount)

    # Clear the asset cache for vault but not adapters.
    self._dirtyAssetCache(True, False)

    # It's our intention to move all funds into the lending adapters so 
    # our target balance is zero.
    self._balanceAdapters( empty(uint256), pregen_info)

    total_after_assets : uint256 = self._totalAssetsCached()
    assert total_after_assets > total_starting_assets, "ERROR - deposit resulted in loss of assets!"
    real_shares : uint256 = convert(convert((total_after_assets - total_starting_assets), decimal) * spot_share_price, uint256)

    if real_shares < transfer_shares:
        assert real_shares >= min_transfer_shares, "ERROR - unable to meet minimum slippage for this deposit!"

        # We'll transfer what was received.
        transfer_shares = real_shares
        log SlippageDeposit(msg.sender, _receiver, _asset_amount, ideal_shares, transfer_shares)

    # Now mint assets to return to investor.    
    self._mint(_receiver, transfer_shares)

    # Update all-time assets deposited for yield tracking.
    self.total_assets_deposited += _asset_amount

    # OLD why was sender twice? - log Deposit(msg.sender, msg.sender, _asset_amount, transfer_shares)
    log Deposit(msg.sender, _receiver, _asset_amount, transfer_shares)

    return transfer_shares


@external
def deposit(_asset_amount: uint256, _receiver: address, _min_shares : uint256 = 0, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> uint256: 
    """
    @notice This function provides a way to transfer an asset amount from message sender to receiver
    @param _asset_amount Number amount of assets to evaluate
    @param _receiver Address of receiver to evaluate
    @param _min_shares Minmum number of shares that is acceptable. If 0 then apply MAX_SLIPPAGE_PERCENT % allowable slippage.
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return Share amount deposited to receiver
    """
    return self._deposit(_asset_amount, _receiver, pregen_info, _min_shares)


@internal
def _withdraw(_asset_amount: uint256,_receiver: address,_owner: address, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS], _min_assets: uint256 = 0) -> uint256:
    min_transfer_balance : uint256 = self._defaultSlippage(_asset_amount, _min_assets)

    # How many shares does it take to get the requested asset amount?
    shares: uint256 = self._convertToShares(_asset_amount, self._totalAssetsCached())
    xcbal : uint256 = self.balanceOf[_owner]

    # Owner has adequate shares?
    assert self.balanceOf[_owner] >= shares, "Owner has inadequate shares for this withdraw."

    # Withdrawl is handled by someone other than the owner?
    if msg.sender != _owner:

        assert self.allowance[_owner][msg.sender] >= shares, "Not authorized to move enough owner's shares."
        self.allowance[_owner][msg.sender] -= shares

    # Burn the shares.
    self.balanceOf[_owner] -= shares    

    self.totalSupply -= shares
    log Transfer(_owner, empty(address), shares)

    # Make sure we have enough assets to send to _receiver. Do a withdraw only balance.
    self._balanceAdapters( _asset_amount, pregen_info, True )

    # Now account for possible slippage.
    current_balance : uint256 = ERC20(asset).balanceOf(self)
    transfer_balance : uint256 = _asset_amount
    if transfer_balance > current_balance:
        # Didn't get as much as we expected. Is it above the minimum?
        assert transfer_balance >= min_transfer_balance, "ERROR - Unable to meet minimum slippage requested for this withdraw."

        # We'll transfer what we received.
        transfer_balance = current_balance
        log SlippageWithdraw(msg.sender, _receiver, _owner, _asset_amount, shares, transfer_balance)

    # Now send assets to _receiver.
    ERC20(asset).transfer(_receiver, transfer_balance)

    # Clear the asset cache for vault but not adapters.
    self._dirtyAssetCache(True, False)

    # Update all-time assets withdrawn for yield tracking.
    self.total_assets_withdrawn += transfer_balance

    log Withdraw(msg.sender, _receiver, _owner, transfer_balance, shares)

    return shares

@external
def withdraw(_asset_amount: uint256,_receiver: address,_owner: address, _min_assets: uint256 = 0, pregen_info: DynArray[Bytes[4096], MAX_ADAPTERS]=empty(DynArray[Bytes[4096], MAX_ADAPTERS])) -> uint256:
    """
    @notice This function provides a way to withdraw an asset amount to receiver
    @param _asset_amount Number amount of assets to evaluate
    @param _receiver Address of receiver to evaluate
    @param _owner Address of owner of assets to evaluate
    @param _min_assets Minimum assets that must be returned (due to slippage) or else reverts. If not specified will be MAX_SLIPPAGE_PERCENT % by default.
    @param pregen_info Optional list of bytes to be sent to each adapter. These are usually off-chain computed results which optimize the on-chain call
    @return Share amount withdrawn to receiver
    """
    return self._withdraw(_asset_amount,_receiver,_owner, pregen_info, _min_assets)

### ERC20 functionality.

@internal
def _transfer(_from: address, _to: address, _value: uint256):
    assert self.balanceOf[_from] >= _value, "ERC20 transfer insufficient funds."
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    log Transfer(_from, _to, _value)


@internal
def _approve(_owner: address, _spender: address, _value: uint256):
    self.allowance[_owner][_spender] = _value
    log Approval(_owner, _spender, _value)


@internal
def _transferFrom(_operator: address, _from: address, _to:address, _value: uint256):
    assert self.balanceOf[_from] >= _value, "ERC20 transferFrom insufficient funds."
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value

    assert self.allowance[_from][_operator] >= _value, "ERC20 transfer insufficient allowance."

    self.allowance[_from][_operator] -= _value
    log Transfer(_from, _to, _value)


@external
def transfer(_to : address, _value : uint256) -> bool:
    """
    @dev Transfer token for a specified address
    @param _to The address to transfer to.
    @param _value The amount to be transferred.
    """
    self._transfer(msg.sender, _to, _value)
    return True


@external
def transferFrom(_from : address, _to : address, _value : uint256) -> bool:
    """
     @dev Transfer tokens from one address to another.
     @param _from address The address which you want to send tokens from
     @param _to address The address which you want to transfer to
     @param _value uint256 the amount of tokens to be transferred
    """
    self._transferFrom(msg.sender, _from, _to, _value)
    return True


@external
def approve(_spender : address, _value : uint256) -> bool:
    """
    @dev Approve the passed address to spend the specified amount of tokens on behalf of msg.sender.
         Beware that changing an allowance with this method brings the risk that someone may use both the old
         and the new allowance by unfortunate transaction ordering. One possible solution to mitigate this
         race condition is to first reduce the spender's allowance to 0 and set the desired value afterwards:
         https://github.com/ethereum/EIPs/issues/20#issuecomment-263524729
    @param _spender The address which will spend the funds.
    @param _value The amount of tokens to be spent.
    """
    self._approve(msg.sender, _spender, _value) 
    return True    

@external
def claimRewards(_adapter: address, reciepent: address):
    assert msg.sender == self.owner, "Only owner can claimRewards!"
    assert _adapter in self.adapters, "Not a valid adapter"
    raw_call(
        _adapter,
        _abi_encode(reciepent, method_id=method_id("claimRewards(address)")),
        max_outsize=0,
        is_delegate_call=True,
        revert_on_failure=True
    )
