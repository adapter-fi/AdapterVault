#pragma version 0.3.10

MAX_ADAPTERS : constant(int128) = 6

struct BalancePool:
    adapter: address
    current: uint256
    ratio: uint256
    target: uint256
    delta: int256
    last_value: uint256  # Remark this out and it works!

@external
@view 
# Only fails when returning with stuff
def getBrokeBalancePoolsWithStuff() -> ( uint256, BalancePool[MAX_ADAPTERS]):
    result : BalancePool[MAX_ADAPTERS] = empty(BalancePool[MAX_ADAPTERS])
    return 0, result
    
@external
@view 
# This breaks here but actually works in my larger code base!
def getBrokeBalancePools() -> ( BalancePool[MAX_ADAPTERS]):
    result : BalancePool[MAX_ADAPTERS] = empty(BalancePool[MAX_ADAPTERS])
    return result
    