#pragma version 0.3.10
#pragma evm-version cancun

# @dev Implementation of ERC-20 token standard.
# @author Takayuki Jimba (@yudetamago)
# https://github.com/ethereum/EIPs/blob/master/EIPS/eip-20.md

from vyper.interfaces import ERC20
from vyper.interfaces import ERC20Detailed

implements: ERC20
implements: ERC20Detailed

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


event Withdraw:
    sender: indexed(address)
    receiver: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256 



name: public(String[64])
symbol: public(String[32])
decimals: public(uint8)

# NOTE: By declaring `balanceOf` as public, vyper automatically generates a 'balanceOf()' getter
#       method to allow access to account balances.
#       The _KeyType will become a required parameter for the getter and it will return _ValueType.
#       See: https://vyper.readthedocs.io/en/v0.1.0-beta.8/types.html?highlight=getter#mappings
balanceOf: public(HashMap[address, uint256])
# By declaring `allowance` as public, vyper automatically generates the `allowance()` getter
allowance: public(HashMap[address, HashMap[address, uint256]])
# By declaring `totalSupply` as public, we automatically create the `totalSupply()` getter
totalSupply: public(uint256)
asset: immutable(address)


#Internal functions


@internal
def _transfer(_from: address, _to: address, _value: uint256):
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    log Transfer(_from, _to, _value)


@internal
def _approve(_owner: address, _spender: address, _value: uint256):
    self.allowance[_owner][_spender] = _value
    log Approval(_owner, _spender, _value)

@internal
def _transferFrom(_operator: address, _from: address, _to:address, _value: uint256):
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    self.allowance[_from][_operator] -= _value
    log Transfer(_from, _to, _value)


@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _asset: address):
    self.name = _name
    self.symbol = _symbol
    self.decimals = _decimals
    self.totalSupply = 0
    asset = _asset

#4626 stuff

@internal
def balances() -> (uint256, uint256):
    return (self.totalSupply,ERC20(asset).balanceOf(self))

#ERC4626 interface

@external
def asset() -> address:
    return asset

@external
@view
def totalAssets() -> uint256:
    return ERC20(asset).balanceOf(self)


@internal
@view
def _convertToShares(_asset_amount: uint256) -> uint256:
    #if no shares are minted, return 1:1 price
    if self.totalSupply == 0:
        return _asset_amount
    #potential runtime err, re: overflow
    share_amt: uint256 = (_asset_amount * self.totalSupply) / ERC20(asset).balanceOf(self)
    return share_amt

@internal
@view
def _convertToAssets(_share_amount: uint256) -> uint256:
    #if no shares are minted, return 1:1 price
    if self.totalSupply == 0:
        return _share_amount
    #potential runtime err, re: overflow
    asset_amt: uint256 = (_share_amount * ERC20(asset).balanceOf(self)) /  self.totalSupply
    return asset_amt

@external
@view
def convertToShares(_asset_amount: uint256) -> uint256:
    return self._convertToShares(_asset_amount)

@external
@view
def convertToAssets(_share_amount: uint256) -> uint256:
    return self._convertToAssets(_share_amount)

@external
@view
def maxDeposit(receiver: address) -> uint256:
    return max_value(uint256)

@external
@view
def previewDeposit(_asset_amount: uint256) -> uint256:
    return self._convertToShares(_asset_amount)

@external
def deposit(_asset_amount: uint256, receiver: address) -> uint256:
    share_amt: uint256 = self._convertToShares(_asset_amount)
    #perform transfer, and assume it works
    ERC20(asset).transferFrom(msg.sender, self, _asset_amount)
    #Mint the shares to receiver
    self._mint(receiver, share_amt)
    log Deposit(msg.sender, receiver, _asset_amount, share_amt)
    return share_amt

@external
@view
def maxMint(receiver: address) -> uint256:
    return max_value(uint256)

@external
@view
def previewMint(_share_amount: uint256) -> uint256:
    return self._convertToAssets(_share_amount)

@external
def mint(_share_amount: uint256, receiver: address) -> uint256:
    asset_amt: uint256 = self._convertToAssets(_share_amount)
    #perform transfer, and assume it works
    ERC20(asset).transferFrom(msg.sender, self, asset_amt)
    #Mint the shares to receiver
    self._mint(receiver, _share_amount)
    log Deposit(msg.sender, receiver, asset_amt, _share_amount)
    return asset_amt

@external
@view
def maxWithdraw(owner: address) -> uint256:
    return self._convertToAssets(self.balanceOf[owner])

@external
@view
def previewWithdraw(_asset_amount: uint256 ) -> uint256:
    return self._convertToShares(_asset_amount)

@external
def withdraw(_asset_amount: uint256, receiver: address, owner: address) -> uint256:
    assert owner == msg.sender, "TODO: approval check"
    share_amt: uint256 = self._convertToShares(_asset_amount)
    assert self.balanceOf[owner] >= share_amt, "balance not enough"
    #Burn shares
    self._burn(owner, share_amt)
    #Send assets to user
    ERC20(asset).transfer(receiver, _asset_amount)
    log Withdraw(msg.sender, receiver, owner, _asset_amount, share_amt)
    return share_amt

@external
@view
def maxRedeem(owner: address) -> uint256:
    return self.balanceOf[owner]

@external
@view
def previewRedeem(_share_amount: uint256) -> uint256:
    return self._convertToAssets(_share_amount)

@external
def redeem(_share_amount: uint256, receiver: address, owner: address) -> uint256:
    assert owner == msg.sender, "TODO: approval check"
    asset_amt: uint256 = self._convertToAssets(_share_amount)
    assert self.balanceOf[owner] >= _share_amount, "balance not enough"
    #Burn shares
    self._burn(owner, _share_amount)
    #Send assets to user
    ERC20(asset).transfer(receiver, asset_amt)
    log Withdraw(msg.sender, receiver, owner, asset_amt, _share_amount)
    return asset_amt
#basic ERC20 stuff below (removed the old minitng capability)

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


@internal
def _mint(_to: address, _value: uint256) -> bool:
    """
    @dev Mint an amount of the token and assigns it to an account.
         This encapsulates the modification of balances such that the
         proper events are emitted.
    @param _to The account that will receive the created tokens.
    @param _value The amount that will be created.
    """
    assert _to != empty(address), "to cannot be empty"
    self.totalSupply += _value
    self.balanceOf[_to] += _value
    log Transfer(empty(address), _to, _value)
    return True


@internal
def _burn(_to: address, _value: uint256):
    """
    @dev Internal function that burns an amount of the token of a given
         account.
    @param _to The account whose tokens will be burned.
    @param _value The amount that will be burned.
    """
    assert _to != empty(address)
    self.totalSupply -= _value
    self.balanceOf[_to] -= _value
    log Transfer(_to, empty(address), _value)


@external
def burn(_value: uint256):
    """
    @dev Burn an amount of the token of msg.sender.
    @param _value The amount that will be burned.
    """
    self._burn(msg.sender, _value)


@external
def burnFrom(_to: address, _value: uint256):
    """
    @dev Burn an amount of the token from a given account.
    @param _to The account whose tokens will be burned.
    @param _value The amount that will be burned.
    """
    self.allowance[_to][msg.sender] -= _value
    self._burn(_to, _value)


#ERC1155 functions calls

# @external
# def safeTransferFrom(_operator: address, _from: address, _to: address, _value: uint256):
#     assert msg.sender == self.minter, "Only minter can safeTransferFrom"
#     self._transferFrom(_operator, _from, _to, _value)


# @external
# def setApprove(_owner: address, _spender: address, _value: uint256):
#     assert msg.sender == self.minter
#     self._approve(_owner, _spender, _value)


