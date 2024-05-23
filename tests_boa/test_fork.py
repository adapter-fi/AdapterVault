import os
import pytest
import boa
from boa.environment import Env

from tests_boa.conftest import forked_env_mainnet

@pytest.fixture
def setup_chain():
    with boa.swap_env(Env()):
        #tests in this file require mainnet block 17024800
        forked_env_mainnet(17024800)
        yield

def test_vitalik_balance(setup_chain):
    vitaliks_loot = boa.env.get_balance(addr="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
    print(vitaliks_loot)
    assert vitaliks_loot == 5149621640741634567741, "Vitalik is rugging EVM state"
