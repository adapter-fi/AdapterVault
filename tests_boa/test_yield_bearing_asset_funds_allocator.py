import os
import pytest
import boa
from decimal import Decimal

# ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
# MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy

@pytest.fixture
def deployer():
    acc = boa.env.generate_address(alias="deployer")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

# @pytest.fixture
# def trader():
#     acc = boa.env.generate_address(alias="trader")
#     boa.env.set_balance(acc, 1000*10**18)
#     return acc

# @pytest.fixture
# def dai(deployer, trader):
#     with boa.env.prank(deployer):
#         erc = boa.load("contracts/test_helpers/ERC20.vy", "DAI Token", "DAI", 18, 1000*10**18, deployer)
#         erc.mint(deployer, 100000)
#         erc.mint(trader, 100000)
#     return erc    

# @pytest.fixture
# def erc20(deployer, trader):
#     with boa.env.prank(deployer):
#         erc = boa.load("contracts/test_helpers/ERC20.vy", "ERC20", "Coin", 18, 1000*10**18, deployer)
#         erc.mint(deployer, 100000)
#         erc.mint(trader, 100000)
#     return erc     

@pytest.fixture
def funds_alloc(deployer):
    with boa.env.prank(deployer):
        f = boa.load("contracts/YieldBearingAssetFundsAllocator.vy")
    return f


def test_is_full_rebalance(funds_alloc):
    assert funds_alloc.internal._is_full_rebalance() == False
