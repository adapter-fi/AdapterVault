import pytest
import ape


@pytest.fixture
def deployer(accounts):
    return accounts[0]


@pytest.fixture
def brokePool(project, deployer):
    v = deployer.deploy(project.BrokeBalancePool, sender=deployer)    
    return v


def test_broken_BalancePool(project, brokePool):
    print("START TEST")
    brokePool.getBrokeBalancePools()

    print("THAT WORKED")

    brokePool.getBrokeBalancePoolsWithStuff()
    print("COMPLETE TEST")  