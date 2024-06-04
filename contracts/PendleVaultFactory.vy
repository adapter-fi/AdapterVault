#pragma version 0.3.10
#pragma evm-version cancun
"""
@title Pendle AdapterVault Factory
@license Copyright 2023, 2024 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Benjamin Scherrey
"""
from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626

owner: public(address)
adapter_vault_blueprint: public(address)
pendle_adapter_blueprint: public(address)
funds_allocator_impl: public(address)
governance_impl: public(address)

pendle_router: public(address)
pendle_router_static: public(address)
pendle_oracle: public(address)

MAX_ADAPTERS : constant(uint256) = 5

event OwnerChanged:
    new_owner: indexed(address)
    old_owner: indexed(address)    

event PendleAdapterVaultDeployed:
    adapter_vault: indexed(address)
    asset: indexed(address)
    pendle_market: address
    adapter_vault_blueprint: address
    pendle_adapter_blueprint: address
    owner: address

struct AdapterStrategy:
    adapter: address
    ratio: uint256    

interface AdapterVault:
    def set_strategy(Proposer: address, Strategies: AdapterStrategy[MAX_ADAPTERS], min_proposer_payout: uint256) -> bool: nonpayable
    def replaceGovernanceContract(NewGovernance: address) -> bool: nonpayable
    def replaceOwner(_new_owner: address) -> bool: nonpayable

@external
def __init__():
    """
    @notice Constructor for 4626the factory contract.
    """
    self.owner = msg.sender

@external
@nonpayable
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

#TODO: owner-only setters for storage

@external
@nonpayable
def deploy_vault(
    _asset: address,
    _pendle_market: address,
    _name: String[64],
    _symbol: String[32],
    _decimals: uint8,
    _max_slippage_percent: decimal,
    _init_mint_amount: uint256
    ):
    """
    @notice deploy a new AdapterVault with single adapter pointing to the mentioned pendle market
    @param _asset the vault will be denominated in.
    @param _pendle_market the vault will invest in
    @param _name of shares token
    @param _symbol identifier of shares token
    @param _decimals increment for division of shares token 
    @param _max_slippage_percent default maximum acceptable slippage for deposits/withdraws as a percentage
    @param _init_mint_amount The amount asset to be deposited, and resulting shares burned.
    """
    assert msg.sender == self.owner, "Only owner may deploy a vault"
    assert _init_mint_amount > 0, "Some amount shares must be burned"
    #TODO: more asserts to ensure required addresses have been populated
    #deploy pendle adapter using blueprint
    adapter: address = create_from_blueprint(
        self.pendle_adapter_blueprint,
        _asset,
        self.pendle_router,
        self.pendle_router_static,
        _pendle_market,
        self.pendle_oracle
    )
    #deploy vault using blueprint
    adapters: DynArray[address, MAX_ADAPTERS] = empty(DynArray[address, MAX_ADAPTERS])
    adapters.append(adapter) 
    vault: address = create_from_blueprint(
        self.adapter_vault_blueprint,
        _name,
        _symbol,
        _decimals,
        _asset,
        adapters,
        self.owner,
        self.funds_allocator_impl,
        _max_slippage_percent
    )
    #initialize the vault with strategy.
    strategy: AdapterStrategy[MAX_ADAPTERS] = empty(AdapterStrategy[MAX_ADAPTERS]) 
    strategy[0].adapter = adapter
    strategy[0].ratio = 1
    AdapterVault(vault).set_strategy(msg.sender, strategy, 0)
    #mint some shares (take asset from owner)
    ERC20(_asset).transferFrom(msg.sender, self, _init_mint_amount)
    ERC4626(vault).deposit(_init_mint_amount, self)
    #burn resulting shares
    ERC20(vault).transfer(empty(address), ERC20(vault).balanceOf(self))
    #assign governance contract
    AdapterVault(vault).replaceGovernanceContract(self.governance_impl)
    #Transfer ownership of vault to owner
    AdapterVault(vault).replaceOwner(self.owner)
    #All done log it
    log PendleAdapterVaultDeployed(
        vault,
        _asset,
        _pendle_market,
        self.adapter_vault_blueprint,
        self.pendle_adapter_blueprint,
        self.owner
    )
