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
        f = boa.load("contracts/FundsAllocator.vy")
    return f

@pytest.fixture
def adapter_zero_loss(deployer, dai, erc20):
    with boa.env.prank(deployer):
        m = boa.load("contracts/adapters/MockSlippageManager.vy")
        a = boa.load("contracts/adapters/MockLPSlippageAdapter.vy", dai, erc20, m)
        a.set_slippage(Decimal(0.0))
    return a

@pytest.fixture
def adapter_two_percent_loss(deployer, dai, erc20):
    with boa.env.prank(deployer):
        m = boa.load("contracts/adapters/MockSlippageManager.vy")
        a = boa.load("contracts/adapters/MockLPSlippageAdapter.vy", dai, erc20, m)
        a.set_slippage(Decimal(2.0))
    return a    

@pytest.fixture
def adapter_five_percent_loss(deployer, dai, erc20):
    with boa.env.prank(deployer):
        m = boa.load("contracts/adapters/MockSlippageManager.vy")
        a = boa.load("contracts/adapters/MockLPSlippageAdapter.vy", dai, erc20, m)
        a.set_slippage(Decimal(5.0))
    return a     


def _add_adapter_to_vault(_vault, _adapter, _deployer, _erc20):
    with boa.env.prank(_deployer):
        pass
        #_vault.add_adapter(_adapter)

    # Adapter needs to approve the vault for ERC20 transfers.
    with boa.env.prank(_adapter.address):
        _erc20.approve(_vault.address, 10*10**18)


@pytest.fixture
def vault(deployer, dai, funds_alloc, gov, adapter_two_percent_loss):
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

    #_add_adapter_to_vault(v, adapter_two_percent_loss, dai, deployer)
    with boa.env.prank(deployer):
        v.add_adapter(adapter_two_percent_loss)

    # Adapter needs to approve the vault for ERC20 transfers.
    with boa.env.prank(adapter_two_percent_loss.address):
        dai.approve(v.address, 10*10**18)           



    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    strategy[0] = (adapter_two_percent_loss.address, 1)

    with boa.env.prank(gov.address):
        v.set_strategy(deployer, strategy, 0)
     

    return v

def test_vault_slippage(vault, deployer, trader, dai, adapter_two_percent_loss):

    with boa.env.prank(trader):
        # deposit & withdraw excercise ERC20 asset transfers and cause
        # balanceAdapters to be called as well.

        dai.approve(vault.address, dai.balanceOf(trader))
        print("\ntest_vault use case:")
        print("adapter now has %s dai." % dai.balanceOf(adapter_two_percent_loss))

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

        shares = vault.deposit(1000, trader)

        print("After 1000 deposit got %s shares for a total balance of %s shares.." % (shares, vault.balanceOf(trader)))

        print("len adapter history = ", adapter_two_percent_loss.slip_history_len())
        percent, qty, usage, val_in, val_out = adapter_two_percent_loss.slip_history(0)
        print("first history = {percent : %s, qty : %s, usage : %s, val_in: %s, val_out : %s}" % (percent, qty, usage, val_in, val_out))

        print("adapter now has %s dai." % dai.balanceOf(adapter_two_percent_loss))

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )
        
        print("Do it again.")

        shares = vault.deposit(1000, trader)

        print("After 1000 deposit got %s shares for a total balance of %s shares.." % (shares, vault.balanceOf(trader)))

        print("len adapter history = ", adapter_two_percent_loss.slip_history_len())
        percent, qty, usage, val_in, val_out = adapter_two_percent_loss.slip_history(0)
        print("first history = {percent : %s, qty : %s, usage : %s, val_in: %s, val_out : %s}" % (percent, qty, usage, val_in, val_out))
        percent, qty, usage, val_in, val_out = adapter_two_percent_loss.slip_history(1)
        print("second history = {percent : %s, qty : %s, usage : %s, val_in: %s, val_out : %s}" % (percent, qty, usage, val_in, val_out))

        print("adapter now has %s dai." % dai.balanceOf(adapter_two_percent_loss))

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

def test_vault_redeem_no_share_slippage(vault, deployer, trader, dai, adapter_two_percent_loss):

    with boa.env.prank(trader):
        # deposit & withdraw excercise ERC20 asset transfers and cause
        # balanceAdapters to be called as well.

        dai.approve(vault.address, dai.balanceOf(trader))
        print("\ntest_vault use case:")
        print("adapter now has %s dai." % dai.balanceOf(adapter_two_percent_loss))

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

@pytest.mark.skip(reason="Fixed mint shares with a slippage adapter isn't actually possible.")
def test_vault_mint_no_share_slippage(vault, deployer, trader, dai, adapter_two_percent_loss):

    with boa.env.prank(trader):
        # deposit & withdraw excercise ERC20 asset transfers and cause
        # balanceAdapters to be called as well.

        dai.approve(vault.address, dai.balanceOf(trader))
        print("\ntest_vault use case:")
        print("adapter now has %s dai." % dai.balanceOf(adapter_two_percent_loss))

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

        assets = vault.mint(1000, trader)

        print("After 1000 mint got %s assets for a total balance of %s shares.." % (assets, vault.balanceOf(trader)))

        assert vault.balanceOf(trader) == 1000

        local, adapters, total, ratios = vault.getCurrentBalances()
        print("vault.getCurrentBalances: local = %s, total = %s." % (local,total) )

        # redeem 100 shares
        assets_moved = vault.redeem(100, trader, trader)      
        
        new_shares = vault.balanceOf(trader)
        new_assets = dai.balanceOf(trader)
        print("After redeeming 100 shares trader now has %s shares." % new_shares)  

        assert shares - 100 == new_shares
        assert new_assets - assets == assets_moved

        