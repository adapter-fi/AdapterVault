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
minter: public(address)
owner: address


#Internal functions


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
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _supply: uint256, _minter: address):
    assert _minter  != ZERO_ADDRESS
    init_supply: uint256 = _supply * 10 ** convert(_decimals, uint256)
    self.name = _name
    self.symbol = _symbol
    self.decimals = _decimals
    self.balanceOf[msg.sender] = init_supply
    self.totalSupply = init_supply
    self.minter = _minter
    self.owner = msg.sender
    log Transfer(ZERO_ADDRESS, msg.sender, init_supply)


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
def mint(_to: address, _value: uint256) -> bool:
    """
    @dev Mint an amount of the token and assigns it to an account.
         This encapsulates the modification of balances such that the
         proper events are emitted.
    @param _to The account that will receive the created tokens.
    @param _value The amount that will be created.
    """
    assert msg.sender == self.minter, "ERC20 only minter can mint!"
    assert _to != ZERO_ADDRESS, "ERC20 can't mint to ZERO_ADDRESS."
    self.totalSupply += _value
    self.balanceOf[_to] += _value
    log Transfer(ZERO_ADDRESS, _to, _value)
    return True


@internal
def _burn(_to: address, _value: uint256):
    """
    @dev Internal function that burns an amount of the token of a given
         account.
    @param _to The account whose tokens will be burned.
    @param _value The amount that will be burned.
    """
    assert _to != ZERO_ADDRESS, "ERC20 can't burn ZERO_ADDRESS."
    assert self.totalSupply >= _value, "ERC20 burning more than total supply."
    assert self.balanceOf[_to] >= _value, "ERC20 burning more than available."
    self.totalSupply -= _value
    self.balanceOf[_to] -= _value
    log Transfer(_to, ZERO_ADDRESS, _value)


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

@external
def safeTransferFrom(_operator: address, _from: address, _to: address, _value: uint256):
    assert msg.sender == self.minter, "Only minter can safeTransferFrom"
    self._transferFrom(_operator, _from, _to, _value)


@external
def setApprove(_owner: address, _spender: address, _value: uint256):
    assert msg.sender == self.minter
    self._approve(_owner, _spender, _value)


@external
def transferMinter(_new_address: address):
    assert msg.sender == self.minter
    self.minter = _new_address


@external
def self_destruct():
    assert msg.sender == self.owner
    selfdestruct(self.owner)
