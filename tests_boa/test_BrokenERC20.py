import os
import pytest
import boa

@pytest.fixture
def deployer():
    acc = boa.env.generate_address(alias="deployer")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

@pytest.fixture
def trader():
    acc = boa.env.generate_address(alias="trader")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

@pytest.fixture
def broke_erc20(deployer, trader):
    with boa.env.prank(deployer):
        b20 = boa.load("contracts/test_helpers/BrokenERC20.vy", "BrokenERC20", "BAD", 18, 1000*10**18, deployer)
    return b20

        