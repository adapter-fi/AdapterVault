import os
import pytest
import boa

from tests_boa.conftest import forked_env_mainnet


def test_vitalik_balance(forked_env_mainnet):
    vitaliks_loot = boa.env.get_balance(addr="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
    print(vitaliks_loot)
    assert vitaliks_loot == 5149621640741634567741, "Vitalik is rugging EVM state"
