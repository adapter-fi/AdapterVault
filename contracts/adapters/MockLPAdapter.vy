#pragma version 0.3.10
#pragma evm-version cancun

from vyper.interfaces import ERC20
# import IAdapter as IAdapter
from IAdapter import IAdapter as IAdapter

interface mintableERC20:
    def mint(_receiver: address, _amount: uint256) -> uint256: nonpayable
    def burn(_value: uint256): nonpayable
    

implements: IAdapter

aoriginalAsset: immutable(address)
awrappedAsset: immutable(address)
adapterLPAddr: immutable(address)


@external
def __init__(_originalAsset: address, _wrappedAsset: address):
    aoriginalAsset = _originalAsset
    awrappedAsset = _wrappedAsset
    adapterLPAddr = self


@external
@pure
def originalAsset() -> address: return aoriginalAsset


@external
@pure
def wrappedAsset() -> address: return awrappedAsset


@internal
@view
def _convertToShares(_asset_amount: uint256) -> uint256:
    shareQty : uint256 = ERC20(awrappedAsset).totalSupply()
    assetQty : uint256 = ERC20(aoriginalAsset).balanceOf(self)

    # If there aren't any shares yet it's going to be 1:1.
    if shareQty == 0 or assetQty == 0: return _asset_amount
    
    sharesPerAsset : decimal = (convert(shareQty, decimal) * 10000.0 / convert(assetQty, decimal)) + 1.0
    return convert(convert(_asset_amount, decimal) * sharesPerAsset / 10000.0, uint256)


@external
@view
def convertToShares(_asset_amount: uint256) -> uint256: return self._convertToShares(_asset_amount)


@internal
@view
def _convertToAssets(_share_amount: uint256) -> uint256:
    # return _share_amount

    shareQty : uint256 = ERC20(awrappedAsset).totalSupply()
    assetQty : uint256 = ERC20(aoriginalAsset).balanceOf(self)

    # If there aren't any shares yet it's going to be 1:1.
    if shareQty == 0 or assetQty == 0: return _share_amount
    
    assetsPerShare : decimal = convert(assetQty, decimal) / convert(shareQty, decimal)
    return convert(convert(_share_amount, decimal) * assetsPerShare, uint256)


@external
@view
def convertToAssets(_share_amount: uint256) -> uint256: return self._convertToAssets(_share_amount)


#How much asset can be withdrawn in a single call
@external
@view
def maxWithdraw() -> uint256: 
    #return self._convertToAssets(ERC20(awrappedAsset).balanceOf(msg.sender))
    return max_value(uint256)


#How much asset can be deposited in a single call
@external
@view
def maxDeposit() -> uint256: 
    return max_value(uint256)


@external
@view
def totalAssets() -> uint256:
    return ERC20(aoriginalAsset).balanceOf(adapterLPAddr)


# Deposit the asset into underlying LP. The tokens must be present inside the 4626 vault.
@external
@nonpayable
def deposit(asset_amount: uint256, pregen_info: Bytes[4096]=empty(Bytes[4096])):
    # Move funds into the LP.
    ERC20(aoriginalAsset).transfer(adapterLPAddr, asset_amount)

    # Return LP wrapped assets to 4626 vault.
    # TODO : Ignore wrapped asset for now!
    # mintableERC20(awrappedAsset).mint(self, self._convertToShares(asset_amount)) 


# Withdraw the asset from the LP to an arbitary address. 
@external
@nonpayable
def withdraw(asset_amount: uint256 , withdraw_to: address, pregen_info: Bytes[4096]=empty(Bytes[4096])) -> uint256 :
    # TODO : Ignore wrapped asset for now!
    # Destroy the wrapped assets
    # shares_owned : uint256 = ERC20(awrappedAsset).balanceOf(self)
    # shares_to_burn : uint256 = self._convertToShares(asset_amount)

    #if shares_to_burn > shares_owned:
    #    assert False, "ACK!" # concat("X ",uint2str(shares_owned), "<", uint2str(shares_to_burn))

    #mintableERC20(awrappedAsset).burn(shares_to_burn)

    assert ERC20(aoriginalAsset).balanceOf(adapterLPAddr) >= asset_amount, "INSUFFICIENT FUNDS!"
    assert ERC20(aoriginalAsset).allowance(adapterLPAddr, self) >= asset_amount, "NO APPROVAL!"

    # Move funds into the destination accout.
    ERC20(aoriginalAsset).transferFrom(adapterLPAddr, withdraw_to, asset_amount)
    
    return asset_amount

@external
def claimRewards(claimant: address):
    pass
