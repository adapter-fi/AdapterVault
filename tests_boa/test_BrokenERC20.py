import os
import pytest
import boa
from decimal import Decimal

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy

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
        b20.mint(trader, 100000)
    return b20

@pytest.fixture
def erc20(deployer, trader):
    with boa.env.prank(deployer):
        erc = boa.load("contracts/test_helpers/ERC20.vy", "ERC20", "Coin", 18, 1000*10**18, deployer)
        erc.mint(deployer, 100000)
    return erc    

@pytest.fixture
def gov(deployer):
    with boa.env.prank(deployer):
        g = boa.load("contracts/Governance.vy", deployer, 21600)
    return g

@pytest.fixture
def funds_alloc(deployer):
    with boa.env.prank(deployer):
        f = boa.load("contracts/FundsAllocator.vy")
    return f

@pytest.fixture
def adapter(deployer, broke_erc20, erc20):
    with boa.env.prank(deployer):
        m = boa.load("contracts/adapters/MockSlippageManager.vy")
        a = boa.load("contracts/adapters/MockLPSlippageAdapter.vy", broke_erc20, erc20, m)

    return a

@pytest.fixture
def vault(deployer, broke_erc20, funds_alloc, gov, adapter):
    with boa.env.prank(deployer):
        v = boa.load(
            "contracts/AdapterVault.vy",
            "TestVault",
            "vault",
            18,
            broke_erc20,
            gov,
            funds_alloc,
            Decimal(2.0)
        )

        v.add_adapter(adapter)

    # Adapter needs to approve the vault for ERC20 transfers.
    with boa.env.prank(adapter.address):
        broke_erc20.approve(v.address, 10*10**18)

    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    #strategy = [(empty(address),0)] * MAX_ADAPTERS
    strategy[0] = (adapter.address, 1)

    with boa.env.prank(gov.address):
        v.set_strategy(deployer, strategy, 0)

    return v

def test_vault(vault, deployer, trader, broke_erc20):
    """
    broke_erc20 is a non-compliant ERC-20 token that doesn't have the required
    boolean return values (much like USDT). Normally this causes Vyper to revert
    during run time but we've altered AdapterVault to be able to deal with this.
    """

    with boa.env.prank(trader):
        # deposit & withdraw excercise ERC20 asset transfers and cause
        # balanceAdapters to be called as well.

        broke_erc20.approve(vault.address, broke_erc20.balanceOf(trader))

        vault.deposit(10000, trader)

        assert vault.balanceOf(trader) == 10000

        vault.withdraw(5000, trader, trader)

        assert vault.balanceOf(trader) == 5000

    with boa.env.prank(deployer):
        # Fake some returns
        broke_erc20.transfer(vault, 10000)
        assert vault.claimable_all_fees_available() > 0

        pre_balance = broke_erc20.balanceOf(deployer)

        # Claiming fees is the last remaining occurrance of ERC20 transfers 
        # within the vault so if this passes we are good.
        vault.claim_all_fees()
        assert broke_erc20.balanceOf(deployer) > pre_balance
