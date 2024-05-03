import pytest
import ape
from tests.conftest import is_not_hard_hat


@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]


@pytest.fixture
def dai(project, deployer, trader):
    ua = deployer.deploy(project.ERC20, "DAI", "DAI", 18, 0, deployer)
    #Transfer some to trader.
    ua.mint(trader, '1000000000 Ether', sender=deployer)
    return ua

def tokendiff(user, tokens, prev={}):
    for token in tokens.keys():
        bal = tokens[token].balanceOf(user) / 10**18
        prev_bal = prev.get(token, 0)
        print("{token}\t: {bal:.4f} ({delta:+.4f})".format(token=token, bal=bal, delta=bal - prev_bal))
        prev[token] = bal
    return prev

@pytest.fixture
def vault_4626(project, deployer, dai, trader):
    v = deployer.deploy(project.Fake4626, "Wrapped DAI", "dDAI4626", 18, dai)
    #Grant allowance for trader
    dai.approve(v, '1000000000 Ether', sender=trader)
    return v

def test_4626(dai, vault_4626, trader):
    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    tokens = {
        "DAI": dai,
        "dDAI4626": vault_4626,
    }
    bal = tokendiff(trader, tokens)
    #Trader deposits 10 DAI
    vault_4626.deposit('10 Ether', trader, sender=trader)
    #Now we "airdrop" 1 DAI to the vault
    dai.transfer(vault_4626, "1 Ether", sender=trader)
    #So now 1 DAI = (1/1.1) DAI since we accured 10% insterst
    assert vault_4626.previewWithdraw(1000000000000000000) == 909090909090909090, "did not get interest"
    #minting should require 10% more DAI
    assert vault_4626.previewMint(1000000000000000000) == 1100000000000000000, "did not get interest"
