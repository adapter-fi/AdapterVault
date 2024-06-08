from tests_boa.conftest import forked_env_mainnet
import os
import pytest
import boa
import json
from boa.environment import Env
from web3 import Web3
import eth_abi
from decimal import Decimal

PENDLE_ROUTER="0x00000000005BBB0EF59571E58418F9a4357b68A0"
PENDLE_ROUTER_STATIC="0x263833d47eA3fA4a30f269323aba6a107f9eB14C"
PENDLE_ORACLE="0x66a1096C6366b2529274dF4f5D8247827fe4CEA8"

MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy


@pytest.fixture
def setup_chain():
    with boa.swap_env(Env()):
        #tests in this file require mainnet block 19850000: May-11-2024 11:13:47 PM +UTC
        forked_env_mainnet(19850000)
        yield

@pytest.fixture
def deployer(setup_chain):
    acc = boa.env.generate_address(alias="deployer")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

@pytest.fixture
def funds_alloc(setup_chain, deployer):
    with boa.env.prank(deployer):
        f = boa.load("contracts/FundsAllocator.vy")
    return f

def _pendle_adapter(deployer, asset, _pendle_market):
    with boa.env.prank(deployer):
        pa = boa.load("contracts/adapters/PendleAdapter.vy", asset, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, _pendle_market, PENDLE_ORACLE)
    return pa

def _adaptervault(deployer, asset, funds_alloc):
    with boa.env.prank(deployer):
        v = boa.load(
            "contracts/AdapterVault.vy",
            "ena-Pendle",
            "pena",
            18,
            asset,
            deployer,
            funds_alloc,
            Decimal(2.0)
        )
    return v

def test_add_pendle_adapter(setup_chain, deployer, funds_alloc):
    asset = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
    market = "0xd0354d4e7bcf345fb117cabe41acadb724eccca2"
    market_future = "0xc374f7ec85f8c7de3207a10bb1978ba104bda3b2"
    adaptervault = _adaptervault(deployer, asset, funds_alloc)
    with boa.env.prank(deployer):
        #add first market
        ad1 = _pendle_adapter(deployer, asset, market)
        adaptervault.add_adapter(ad1)
        #add second market    
        ad2 = _pendle_adapter(deployer, asset, market_future)
        adaptervault.add_adapter(ad2)
        #Try adding copy of first market
        ad1_dupe = _pendle_adapter(deployer, asset, market)
        with boa.reverts("incoming token already handled"):
            adaptervault.add_adapter(ad1_dupe)
        #Try replacing adapters
        adaptervault.swap_adapters(ad1, ad1_dupe)
        #Try swapping between different pendle market adapters
        with boa.reverts("incoming token already handled"):
            adaptervault.swap_adapters(ad2, ad1)
