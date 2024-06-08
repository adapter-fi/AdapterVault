import os
import pytest
import boa
import json
from boa.environment import Env
from web3 import Web3
import eth_abi
from decimal import Decimal

from tests_boa.conftest import forked_env_mainnet

PENDLE_ROUTER="0x00000000005BBB0EF59571E58418F9a4357b68A0"
NOTHING="0x0000000000000000000000000000000000000000"
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
def governance(setup_chain):
    #Just using EOA for this
    acc = boa.env.generate_address(alias="governance")
    boa.env.set_balance(acc, 1000*10**18)
    return acc

@pytest.fixture
def attacker(setup_chain):
    acc = boa.env.generate_address(alias="attacker")
    boa.env.set_balance(acc, 1000*10**18)
    return acc


@pytest.fixture
def steth(setup_chain, trader):
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
    st = factory.at(STETH)
    #Trader needs to acquire some ETH, dunno how
    abi_encoded = eth_abi.encode(['address', 'uint256'], [trader, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()])

    boa.env.set_storage(
        boa.util.abi.Address(STETH).canonical_address,
        Web3.to_int(storage_slot),
        5000 * 10**18
    )
    print(st.balanceOf(trader))
    print(boa.env.get_balance(trader))
    assert st.balanceOf(trader) > 5000 * 10**18, "Trader did not get 'airdrop'"
    return st

@pytest.fixture
def pt(setup_chain):
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
    return factory.at(PENDLE_PT)

@pytest.fixture
def pendleRouter(setup_chain):
    with open("contracts/vendor/IPAllActionV3.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="IPAllActionV3")
    return factory.at(PENDLE_ROUTER)

@pytest.fixture
def pendleMarket(setup_chain):
    with open("contracts/vendor/IPMarketV3.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="IPMarketV3")
    return factory.at(PENDLE_MARKET)

@pytest.fixture
def pendleOracle(setup_chain, pendleMarket):
    with open("contracts/vendor/PendlePtLpOracle.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="PendlePtLpOracle")
    oracle = factory.at(PENDLE_ORACLE)
    increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(PENDLE_MARKET, 1200)
    if increaseCardinalityRequired:
        pendleMarket.increaseObservationsCardinalityNext(cardinalityRequired)
        print("cardinality increased")
    #just in case, simulate passage of time
    boa.env.time_travel(seconds=1200)
    increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(PENDLE_MARKET, 1200)
    print(increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied)
    assert increaseCardinalityRequired==False, "increaseCardinality failed"
    assert oldestObservationSatisfied==True, "oldestObservation is not Satisfied"
    return oracle

@pytest.fixture
def vault_blueprint(setup_chain):
    f = boa.load_partial("contracts/AdapterVault.vy")
    return f.deploy_as_blueprint()

@pytest.fixture
def pendle_adapter_blueprint(setup_chain):
    f = boa.load_partial("contracts/adapters/PendleAdapter.vy")
    return f.deploy_as_blueprint()


@pytest.fixture
def pendle_factory(setup_chain, deployer, steth, pendleOracle):
    with boa.env.prank(deployer):
        pa = boa.load("contracts/PendleVaultFactory.vy")
    return pa

@pytest.fixture
def funds_alloc(setup_chain, deployer):
    with boa.env.prank(deployer):
        f = boa.load("contracts/FundsAllocator.vy")
    return f


def test_vault_factory(setup_chain, pendle_factory, deployer, steth, trader, vault_blueprint, pendle_adapter_blueprint, funds_alloc, governance):
    #Test only owner can change owner
    with boa.env.prank(trader):
        with boa.reverts("Only existing owner can replace the owner."):
            pendle_factory.replace_owner(trader)
        with boa.reverts("Only owner can update contracts"):
            pendle_factory.update_blueprints(vault_blueprint, pendle_adapter_blueprint)
        with boa.reverts("Only owner can update contracts"):
            pendle_factory.update_funds_allocator(funds_alloc)
        with boa.reverts("Only owner can update contracts"):
            pendle_factory.update_governance(governance)
        with boa.reverts("Only owner can update contracts"):
            pendle_factory.update_pendle_contracts(
                PENDLE_ROUTER,
                PENDLE_ROUTER_STATIC,
                PENDLE_ORACLE
            )
    with boa.env.prank(deployer):
        pendle_factory.replace_owner(trader)

    #Now trader should be able to do stuff, but with missing bits
    with boa.env.prank(trader):
        with boa.reverts("adapter_vault_blueprint must be defined"):
            pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        pendle_factory.update_blueprints(vault_blueprint, NOTHING)
        with boa.reverts("pendle_adapter_blueprint must be defined"):
            pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        pendle_factory.update_blueprints(vault_blueprint, pendle_adapter_blueprint)
        with boa.reverts("funds_allocator_impl must be defined"):
            pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        pendle_factory.update_funds_allocator(funds_alloc)
        with boa.reverts("governance_impl must be defined"):
            pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        pendle_factory.update_governance(governance)
        with boa.reverts("pendle_router must be defined"):
            pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        pendle_factory.update_pendle_contracts(
            PENDLE_ROUTER,
            NOTHING,
            NOTHING
        )
        with boa.reverts("pendle_router_static must be defined"):
            pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        pendle_factory.update_pendle_contracts(
            PENDLE_ROUTER,
            PENDLE_ROUTER_STATIC,
            NOTHING
        )
        with boa.reverts("pendle_oracle must be defined"):
            pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        pendle_factory.update_pendle_contracts(
            PENDLE_ROUTER,
            PENDLE_ROUTER_STATIC,
            PENDLE_ORACLE
        )
        steth.approve(pendle_factory, 10**9)
        #Finally we can deploy
        pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
        #TODO: Fetch logs... 
        #TODO: Validate the adapter and vault
