#pragma version 0.3.10
#pragma evm-version cancun
"""
@title ERC4626 Adapter
@license Copyright 2023, 2024 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Sajal Kayan
"""

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626
# import IAdapter as IAdapter
from IAdapter import IAdapter as IAdapter

interface mintableERC20:
    def mint(_receiver: address, _amount: uint256) -> uint256: nonpayable
    def burn(_value: uint256): nonpayable
    


implements: IAdapter

Asset: immutable(address)
Share: immutable(address)
adapterAddr: immutable(address)
signal_neutral: immutable(bool)

@external
def __init__(_originalAsset: address, _wrappedAsset: address, _signal_neutral: bool):
    Asset = _originalAsset
    Share = _wrappedAsset
    adapterAddr = self
    signal_neutral = _signal_neutral


@external
@pure
def asset() -> address: return Asset

@external
@pure
def wrappedAsset() -> address: return Share


@internal
@view
def _convertToShares(_asset_amount: uint256) -> uint256:
    return ERC4626(Share).convertToShares(_asset_amount)

# @external
# @view
# def convertToShares(_asset_amount: uint256) -> uint256: return self._convertToShares(_asset_amount)


@internal
@view
def _convertToAssets(_share_amount: uint256) -> uint256:
    return ERC4626(Share).convertToAssets(_share_amount)


# @external
# @view
# def convertToAssets(_share_amount: uint256) -> uint256: return self._convertToAssets(_share_amount)


#How much asset can be withdrawn in a single call
@external
@view
def maxWithdraw() -> uint256: 
    return ERC4626(Share).maxWithdraw(self.vault_location())

#Magic value to signal to funds allocator that the current adapter is the neutral one
NEUTRAL_ADAPTER_MAX_DEPOSIT : constant(uint256) = 2**255 - 43

#How much asset can be deposited in a single call
@external
@view
def maxDeposit() -> uint256:
    if signal_neutral:
        return NEUTRAL_ADAPTER_MAX_DEPOSIT
    else:
        max_deposit: uint256 = ERC4626(Share).maxDeposit(self.vault_location())
        #Added protection in case underlying vault's result happens to match our magic number
        if max_deposit == NEUTRAL_ADAPTER_MAX_DEPOSIT:
            max_deposit -= 1
        return max_deposit

@external
@view
def totalAssets() -> uint256:
    #return ERC20(Asset).balanceOf(adapterAddr)
    return self._convertToAssets(ERC20(Share).balanceOf(self.vault_location()))


# Deposit the asset into underlying LP. The tokens must be present inside the 4626 vault.
@external
@nonpayable
def deposit(_asset_amount: uint256, _pregen_info: Bytes[4096]=empty(Bytes[4096])):
    # Move funds into the LP. These map 1:1 with assets when deposited.
    ERC20(Asset).approve(Share, _asset_amount)
    initial : uint256 = ERC20(Share).balanceOf(self)
    ERC4626(Share).deposit(_asset_amount, self)

# Withdraw the asset from the LP to an arbitary address. 
@external
@nonpayable
def withdraw(_asset_amount: uint256 , _withdraw_to: address, 
             _pregen_info: Bytes[4096]=empty(Bytes[4096])) -> uint256 :
    return ERC4626(Share).withdraw(_asset_amount, _withdraw_to, _withdraw_to)

@external
def claimRewards(claimant: address):
    pass

@external
@view
def managed_tokens() -> DynArray[address, 10]:
    ret: DynArray[address, 10] = empty(DynArray[address, 10])
    ret.append(Share)
    return ret


#Workaround because vyper does not allow doing delegatecall from inside view.
#we do a static call instead, but need to fix the correct vault location for queries.
@internal
@view
def vault_location() -> address:
    if self == adapterAddr:
        #if "self" is adapter, meaning this is not delegate call and we treat msg.sender as the vault
        return msg.sender
    #Otherwise we are inside DELEGATECALL, therefore self would be the 4626
    return self
