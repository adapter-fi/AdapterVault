import os
import pytest
import boa
import json
from boa.environment import Env

from tests_boa.conftest import forked_env_mainnet

PENDLE_ROUTER="0x00000000005BBB0EF59571E58418F9a4357b68A0"
PENDLE_ROUTER_STATIC="0x263833d47eA3fA4a30f269323aba6a107f9eB14C"
PENDLE_MARKET="0xd0354d4e7bcf345fb117cabe41acadb724eccca2" #Pendle: PT-stETH-26DEC24/SY-stETH Market Token
STETH="0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
PENDLE_PT="0x7758896b6AC966BbABcf143eFA963030f17D3EdF"
PENDLE_ORACLE="0x66a1096C6366b2529274dF4f5D8247827fe4CEA8"

MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935



@pytest.fixture
def setup_chain():
    with boa.swap_env(Env()):
        #tests in this file require mainnet block 19675100: Apr-17-2024 12:09:23 PM +UTC
        forked_env_mainnet(19675100)
        yield

@pytest.fixture
def deployer(setup_chain):
    acc = boa.env.generate_address(alias="deployer")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

@pytest.fixture
def trader(setup_chain):
    acc = boa.env.generate_address(alias="trader")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

@pytest.fixture
def steth(setup_chain, trader):
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
    steth = factory.at(STETH)
    #Trader needs to aquire some ETH, dunno how
    print(steth.balanceOf(trader))
    print(boa.env.get_balance(trader))

def test_foo(steth):
    pass
