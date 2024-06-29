import os
import pytest
import boa
import json
from boa.environment import Env
from web3 import Web3
import eth_abi


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
def pendle_adapter(setup_chain, deployer, steth, pendleOracle):
    with boa.env.prank(deployer):
        pa = boa.load("contracts/adapters/PendleAdapter.vy", steth, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, PENDLE_MARKET, PENDLE_ORACLE)
    return pa

def test_pendle_adapter_standalone(pendle_adapter, pt, steth, pendleRouter, trader, pendleOracle):
    with boa.env.prank(pendle_adapter.address):
        assert pendle_adapter.totalAssets() == 0, "Asset balance should be 0"
        assert pendle_adapter.maxWithdraw() == 0, "maxWithdraw should be 0"
        assert pendle_adapter.maxDeposit() > 0, "maxDeposit should > 0"
    assert pt.balanceOf(pendle_adapter) == 0, "PT balance incorrect"
    with boa.env.prank(trader):
        steth.approve(pendleRouter, 100*10**18)

        ap = (
            0, #guessMin
            MAX_UINT256, #guessMax
            0, #guessOffchain
            256, #maxIteration
            10**14 #eps
        )
        ti = (
            STETH, #tokenIn
            100*10**18, #netTokenIn
            STETH, #tokenMintSy
            "0x0000000000000000000000000000000000000000", #pendleSwap
            (
                0,
                "0x0000000000000000000000000000000000000000",
                b"",
                False
            ) #swapData
        )
        limit = (
            "0x0000000000000000000000000000000000000000", #limitRouter
            0, #epsSkipMarket
            [], #normalFills
            [], #flashFills
            b"" #optData
        )

        pendleRouter.swapExactTokenForPt(trader, PENDLE_MARKET, 0, ap, ti, limit)
    
        pt_bal = pt.balanceOf(trader)
        assert pt_bal > 100*10**18, "did not get enough PT"
        print("pt_bal", pt_bal)
        oracle_price = pendleOracle.getPtToAssetRate(PENDLE_MARKET, 900)
        total_assets = pendle_adapter.totalAssets()

        assert total_assets == pytest.approx( (pt_bal * oracle_price) // 10**18), "total_assets incorrect"
        assert total_assets < 100*10**18, "total_assets should be less than 100 stETH, due to slippage"
        print(total_assets / 10**18)
        assert pendle_adapter.maxWithdraw() == total_assets, "max withdraw must equal total assets"
        assert pendle_adapter.maxDeposit() == MAX_UINT256, "max deposit should be unlimited"


        boa.env.time_travel(seconds=60*60*24*30*9)
        assert pendle_adapter.maxDeposit() == 0, "max deposit should be 0 post-maturity"
        total_assets = pendle_adapter.totalAssets()
        pt_bal = pt.balanceOf(trader)

        assert total_assets == pytest.approx(pt_bal), "PT should be pegged to asset post-maturity"
        assert pendle_adapter.maxWithdraw() == total_assets, "max withdraw must equal total assets"


def test_pendle_adapter_mint(pendle_adapter,  pt, steth, pendleRouter, trader):
    with boa.env.prank(trader):
        #Trader direct mint 1 stETH
        steth.transfer(pendle_adapter, 1*10**18)
        pendle_adapter.deposit(1*10**18, gas=3000000)
        print("no pregen", pendle_adapter._computation.net_gas_used)

        #Compute pregen
        pregen_bytes = pendle_adapter.generate_pregen_info(10**18)
        steth.transfer(pendle_adapter, 1*10**18)
        pendle_adapter.deposit(1*10**18, pregen_bytes, gas=3000000)
        print("pregen", pendle_adapter._computation.net_gas_used)



