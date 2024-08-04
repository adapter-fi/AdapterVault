#pragma version 0.3.10
#pragma evm-version cancun

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626
# import IAdapter as IAdapter
from IAdapter import IAdapter as IAdapter

##
## Must match AdapterVault.vy
##

MAX_ADAPTERS : constant(uint256) = 5 

interface mintableERC20:
    def mint(_receiver: address, _amount: uint256) -> uint256: nonpayable
    def burn(_value: uint256): nonpayable
    


implements: IAdapter

Asset: immutable(address)
Share: immutable(address)
adapterLPAddr: immutable(address)


@external
def __init__(_originalAsset: address, _wrappedAsset: address):
    Asset = _originalAsset
    Share = _wrappedAsset
    adapterLPAddr = self


@external
@pure
def originalAsset() -> address: return Asset


@external
@pure
def wrappedAsset() -> address: return Share


@internal
@view
def _convertToShares(_asset_amount: uint256) -> uint256:
    return ERC4626(Share).convertToShares(_asset_amount)

@external
@view
def convertToShares(_asset_amount: uint256) -> uint256: return self._convertToShares(_asset_amount)


@internal
@view
def _convertToAssets(_share_amount: uint256) -> uint256:
    return ERC4626(Share).convertToAssets(_share_amount)


@external
@view
def convertToAssets(_share_amount: uint256) -> uint256: return self._convertToAssets(_share_amount)


#How much asset can be withdrawn in a single call
@external
@view
def maxWithdraw() -> uint256: 
    return self._convertToAssets(ERC20(Share).balanceOf(self.vault_location()))


NEUTRAL_ADAPTER_MAX_DEPOSIT : constant(uint256) = 2**255 - 43

#How much asset can be deposited in a single call
@external
@view
def maxDeposit() -> uint256: 
    return NEUTRAL_ADAPTER_MAX_DEPOSIT


@external
@view
def totalAssets() -> uint256:
    #return ERC20(Asset).balanceOf(adapterLPAddr)
    return self._convertToAssets(ERC20(Share).balanceOf(self.vault_location()))


# Deposit the asset into underlying LP. The tokens must be present inside the 4626 vault.
@external
@nonpayable
def deposit(_asset_amount: uint256, _pregen_info: Bytes[4096]=empty(Bytes[4096])):
    # Move funds into the LP. These map 1:1 with assets when deposited.
    ERC20(Asset).approve(Share, _asset_amount)
    initial : uint256 = ERC20(Share).balanceOf(self)
    ERC4626(Share).deposit(_asset_amount, self)
    assert ERC20(Share).balanceOf(self) == initial + _asset_amount, "DIDN'T WORK!"


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
    if self == adapterLPAddr:
        #if "self" is adapter, meaning this is not delegate call and we treat msg.sender as the vault
        return msg.sender
    #Otherwise we are inside DELEGATECALL, therefore self would be the 4626
    return self
