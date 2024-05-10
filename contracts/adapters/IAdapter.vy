#pragma version 0.3.10
#pragma evm-version cancun
"""
@title AdapterVault Adapter interface
@license Copyright 2023, 2024 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Sajal Kayan, Benjamin Scherrey
"""

#Declaring interface in this format allows it to be "compiled", so we can use its ABI from python side
#One happy side-effect is now "implements" bit is enforced in other contracts.

# How much asset can be withdrawn in a single call
@external
@view
def maxWithdraw() -> uint256:
    """
    @notice returns the maximum possible asset amount thats withdrawable from this adapter
    @dev
        This method returns a valid response if it has been DELEGATECALL or 
        STATICCALL-ed from the AdapterVault contract it services. It is not intended
        to be called directly by third parties.
    """
    return max_value(uint256)

# How much asset can be deposited in a single call
@external
@view
def maxDeposit() -> uint256:
    """
    @notice returns the maximum possible asset amount thats depositable to this adapter
    @dev
        This method returns a valid response if it has been DELEGATECALL or 
        STATICCALL-ed from the AdapterVault contract it services. It is not intended
        to be called directly by third parties.
    """
    return max_value(uint256)

# How much asset this LP is responsible for.
@external
@view
def totalAssets() -> uint256:
    """
    @notice returns the balance currently held by the adapter.
    @dev
        This method returns a valid response if it has been DELEGATECALL or
        STATICCALL-ed from the AdapterVault contract it services. It is not
        intended to be called directly by third parties.
    """
    return 0


# Deposit the asset into underlying LP. The tokens must be present inside the 4626 vault.
@external
def deposit(asset_amount: uint256, pregen_info: Bytes[4096]=empty(Bytes[4096])):
    """
    @notice deposit asset into underlying LP.
    @param asset_amount The amount of asset we want to deposit into underlying LP
    @dev
        This method is only valid if it has been DELEGATECALL-ed
        from the AdapterVault contract it services. It is not intended to be
        called directly by third parties.
    """
    pass


# Withdraw the asset from the LP to an arbitary address. 
@external
def withdraw(asset_amount: uint256 , withdraw_to: address, pregen_info: Bytes[4096]=empty(Bytes[4096])) -> uint256 :
    """
    @notice withdraw asset from underlying LP.
    @param asset_amount The amount of asset we want to withdraw from underlying LP
    @param withdraw_to The ultimate reciepent of the withdrawn assets
    @dev
        This method is only valid if it has been DELEGATECALL-ed
        from the AdapterVault contract it services. It is not intended to be
        called directly by third parties.
    """
    return asset_amount

@external
def claimRewards(claimant: address):
    """
    @notice hook to claim reward from underlying LP
    @dev
        This method is DELEGATECALL'd from vault into adapter.
        The functionality varries per adapter. In case the rewards cannot
        be re-deposited into the vault, it would transfer those to "claimant"
        i.e. vault owner for further swapping.
    """
    pass
