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
def dai(deployer, trader):
    with boa.env.prank(deployer):
        erc = boa.load("contracts/test_helpers/ERC20.vy", "DAI Token", "DAI", 18, 1000*10**18, deployer)
        erc.mint(deployer, 100000)
        erc.mint(trader, 100000)
    return erc    

@pytest.fixture
def erc20(deployer, trader):
    with boa.env.prank(deployer):
        erc = boa.load("contracts/test_helpers/ERC20.vy", "ERC20", "Coin", 18, 1000*10**18, deployer)
        erc.mint(deployer, 100000)
        erc.mint(trader, 100000)
    return erc     

@pytest.fixture
def gov(deployer):
    with boa.env.prank(deployer):
        g = boa.load("contracts/Governance.vy", deployer, 21600)
    return g

@pytest.fixture
def funds_alloc(deployer):
    with boa.env.prank(deployer):
        f = boa.load("contracts/YieldBearingAssetFundsAllocator.vy")
    return f

@pytest.fixture
def lp_vault(deployer, dai, funds_alloc, gov):
    with boa.env.prank(deployer):
        v = boa.load(
            "contracts/AdapterVault.vy",
            "LPVault",
            "LPvault",
            18,
            dai,
            gov,
            funds_alloc,
            Decimal(3.0)
        )

    return v


@pytest.fixture
def neutral_adapter(deployer, lp_vault, dai):
    with boa.env.prank(deployer):
        v = boa.load(
            "contracts/adapters/NeutralAdapter.vy",
            dai,
            lp_vault)
    return v




@pytest.fixture
def vault(deployer, dai, funds_alloc, gov, neutral_adapter):
    with boa.env.prank(deployer):
        v = boa.load(
            "contracts/AdapterVault.vy",
            "TestVault",
            "vault",
            18,
            dai,
            gov,
            funds_alloc,
            Decimal(3.0)
        )

    return v

def test_min_vault_redeem_no_share_slippage(vault, deployer, trader, dai):

    with boa.env.prank(trader):
        # deposit & withdraw excercise ERC20 asset transfers and cause
        # balanceAdapters to be called as well.

        dai.approve(vault.address, dai.balanceOf(trader))
        print("\ntest_vault use case:")

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

        shares = vault.deposit(1000, trader)
        assets = dai.balanceOf(trader)

        print("After 1000 deposit got %s shares for a total balance of %s shares.." % (shares, vault.balanceOf(trader)))

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

        # redeem 100 shares
        assets_moved = vault.redeem(100, trader, trader)      
        
        new_shares = vault.balanceOf(trader)
        new_assets = dai.balanceOf(trader)
        print("After redeeming 100 shares trader now has %s shares." % new_shares)  

        assert shares - 100 == new_shares
        assert new_assets - assets == assets_moved


def test_min_vault_mint_no_share_slippage(vault, deployer, trader, dai):

    with boa.env.prank(trader):
        # deposit & withdraw excercise ERC20 asset transfers and cause
        # balanceAdapters to be called as well.

        dai.approve(vault.address, dai.balanceOf(trader))
        print("\ntest minimal vault use case:")

        print("Trader starts with %s shares." % vault.balanceOf(trader))

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

        assets = dai.balanceOf(trader)
        assets_minted = vault.mint(1000, trader)
        shares = vault.balanceOf(trader)

        print("After 1000 mint got %s assets for a total balance of %s shares.." % (assets_minted, vault.balanceOf(trader)))

        assert vault.balanceOf(trader) == 1000

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

        # redeem 100 shares
        assets_moved = vault.redeem(100, trader, trader)      
        
        new_shares = vault.balanceOf(trader)
        new_assets = dai.balanceOf(trader)
        print("After redeeming 100 shares trader now has %s shares." % new_shares)  

        assert shares - 100 == new_shares
        assert assets - new_assets == assets_minted - assets_moved
        assert assets_moved == 100

        print("Should be no returns.")

        assert vault.totalReturns() == 0
        assert vault.claimable_all_fees_available() == 0