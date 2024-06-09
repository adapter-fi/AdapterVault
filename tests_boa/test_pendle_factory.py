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
PENDLE_MARKET="0xD0354D4e7bCf345fB117cabe41aCaDb724eccCa2" #Pendle: PT-stETH-26DEC24/SY-stETH Market Token
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

def access_vault(addr):
    f = boa.load_partial("contracts/AdapterVault.vy")
    return f.at(addr)


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
        vault_addr = pendle_factory.deploy_pendle_vault(STETH, PENDLE_MARKET, "steth blah", "psteth", 18, Decimal(2.0), 10**9)
    #Fetch logs...
    logs = pendle_factory.get_logs(include_child_logs=False)
    assert len(logs) == 1
    #TODO: Parse logs...
    deployed_log = logs[0]
    print(deployed_log)
    print(deployed_log.args)
    assert "PendleAdapterVaultDeployed" in str(deployed_log.event_type), "event mismatch"
    assert deployed_log.topics[0] == vault_addr, "event mismatch"
    assert deployed_log.topics[1] == steth.address, "event mismatch"
    assert deployed_log.args[0] == PENDLE_MARKET, "event mismatch"
    assert deployed_log.args[1] == vault_blueprint.address, "event mismatch"
    assert deployed_log.args[2] == pendle_adapter_blueprint.address, "event mismatch"
    assert deployed_log.args[3] == trader, "event mismatch"
    #Validate the adapter and vault
    print("deployment cost", pendle_factory._computation.get_gas_used())
    vault = access_vault(vault_addr)
    assert vault.name() == "steth blah", "name incorrect"
    assert vault.decimals() == 18, "decimals incorrect"
    assert vault.symbol() == "psteth", "symbol incorrect"
    assert vault.governance() == governance, "governance incorrect"
    assert vault.owner() == trader, "owner incorrect"
    assert vault.eval("MAX_SLIPPAGE_PERCENT")  == Decimal(2.0), "MAX_SLIPPAGE_PERCENT incorrect"
    assert vault.asset() == STETH, "asset incorrect"
    assert vault.funds_allocator() == funds_alloc.address, "funds_allocator incorrect"
    assert vault.current_proposer() == trader, "current_proposer incorrect"
    assert vault.total_assets_deposited() == pytest.approx(10**9, 0.02), "total_assets_deposited incorrect"
    assert vault.total_assets_withdrawn() == 0, "total_assets_withdrawn incorrect"
    assert vault.total_yield_fees_claimed() == 0, "total_yield_fees_claimed incorrect"
    assert vault.total_strategy_fees_claimed() == 0, "total_strategy_fees_claimed incorrect"
    assert vault.totalSupply() == pytest.approx(10**9, 0.02), "totalSupply incorrect"
