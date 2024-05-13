from ..conftest import forked_env_mainnet
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

def _steth(trader, addr):
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
    st = factory.at(addr)
    #Trader needs to acquire some ETH, dunno how
    abi_encoded = eth_abi.encode(['address', 'uint256'], [trader, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()])

    boa.env.set_storage(
        boa.util.abi.Address(addr).canonical_address,
        Web3.to_int(storage_slot),
        5000 * 10**18
    )
    print(st.balanceOf(trader))
    print(boa.env.get_balance(trader))
    assert st.balanceOf(trader) > 5000 * 10**18, "Trader did not get 'airdrop'"
    return st

def _ena(trader, addr):
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
    en = factory.at(addr)
    #Trader needs to acquire some ETH, dunno how
    abi_encoded = eth_abi.encode(['address', 'uint256'], [trader, 2])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()])

    # print("en", en.balanceOf("0xd4b34207a671b813b5e66d31ea0b0a9849de9bc1"))

    # for x in range(0,10):
    #     print(x)
    #     abi_encoded = eth_abi.encode(['address', 'uint256'], ["0xd4B34207a671b813B5E66d31EA0b0A9849de9bc1", x])
    #     storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()])
    #     print(boa.env.evm.vm.state.get_storage(boa.util.abi.Address(ENA).canonical_address, Web3.to_int(storage_slot)))

    # return
    boa.env.set_storage(
        addr,
        Web3.to_int(storage_slot),
        5000 * 10**18
    )
    print(en.balanceOf(trader))
    print(boa.env.get_balance(trader))
    assert en.balanceOf(trader) == 5000 * 10**18, "Trader did not get 'airdrop'"
    return en

def _pendleOracle(pendleMarket, _PENDLE_ORACLE):
    with open("contracts/vendor/PendlePtLpOracle.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="PendlePtLpOracle")
    oracle = factory.at(_PENDLE_ORACLE)
    increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(pendleMarket, 1200)
    if increaseCardinalityRequired:
        pendleMarket.increaseObservationsCardinalityNext(cardinalityRequired)
        print("cardinality increased")
    #just in case, simulate passage of time
    boa.env.time_travel(seconds=1200)
    increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(pendleMarket, 1200)
    print(increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied)
    assert increaseCardinalityRequired==False, "increaseCardinality failed"
    assert oldestObservationSatisfied==True, "oldestObservation is not Satisfied"
    return oracle

def pendle_Market(_pendle_market):
    with open("contracts/vendor/IPMarketV3.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="IPMarketV3")
    return factory.at(_pendle_market)

def _pendle_adapter(deployer, asset, _pendle_market):
    with boa.env.prank(deployer):
        pa = boa.load("contracts/adapters/PendleAdapter.vy", asset, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, _pendle_market, PENDLE_ORACLE)
    return pa

@pytest.fixture
def funds_alloc(setup_chain, deployer):
    with boa.env.prank(deployer):
        f = boa.load("contracts/FundsAllocator.vy")
    return f

def _adaptervault(deployer, asset, trader, funds_alloc):
    with boa.env.prank(deployer):
        v = boa.load(
            "contracts/AdapterVault.vy",
            "ena-Pendle",
            "pena",
            18,
            asset,
            [],
            deployer,
            funds_alloc,
            Decimal(2.0)
        )
    return v


def pendle_pt(_pendle_pt):
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
        factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
        return factory.at(_pendle_pt)

def market_test(_pendle_pt, asset, trader, deployer, _pendle_market, funds_alloc, _PENDLE_ORACLE):

    pt = pendle_pt(_pendle_pt)
    pendleMarket = pendle_Market(_pendle_market)
    pendleOracle = _pendleOracle(pendleMarket, _PENDLE_ORACLE)
    pendle_adapter = _pendle_adapter(deployer, asset, _pendle_market)
    adaptervault = _adaptervault(deployer, asset, trader, funds_alloc)
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    strategy[0] = (pendle_adapter.address, 1)

    with boa.env.prank(deployer):
        adaptervault.set_strategy(deployer, strategy, 0)
        ret = adaptervault.add_adapter(pendle_adapter.address) 
        assert ret == True
    
    with boa.env.prank(trader):
        asset.approve(adaptervault, 1*10**18)
        bal_pre = asset.balanceOf(trader)
        ex_rate = pendleOracle.getPtToAssetRate(_pendle_market, 1200)
        adaptervault.deposit(1*10**18, trader)
        print("GAS USED FOR PENDLE DEPOSIT = ", adaptervault._computation.net_gas_used) 
        deducted = bal_pre - asset.balanceOf(trader)
        print(deducted)
        assert deducted == 1*10**18, "Invalid amount got deducted"
        print(pt.balanceOf(adaptervault))
        traderbal = adaptervault.balanceOf(trader)
        print(traderbal)
        trader_asset_bal = adaptervault.convertToAssets(traderbal)
        print(trader_asset_bal)
        total_assets = adaptervault.totalAssets()
        print(total_assets)
        #since trader is the first depositor, everything in the vault belongs to trader
        assert total_assets == trader_asset_bal, "Funds missing"
        #Ensure slippage is within limits (or else the vault would have reverted...)
        assert trader_asset_bal > deducted - (deducted * 0.02), "slipped beyond limits"
        assert adaptervault.claimable_yield_fees_available() == 0, "there should be no yield"

        #Move a month into future, to get yields
        #This should put us at around May 17th, and since pendle's TWAP accounts for interest, we should have yield
        boa.env.time_travel(seconds=60*60*24*30)
        traderbal = adaptervault.balanceOf(trader)
        trader_asset_bal_new = adaptervault.convertToAssets(traderbal)
        print(trader_asset_bal_new)
        assert trader_asset_bal_new > trader_asset_bal, "new trader balance should be higher because of yield"
        assert adaptervault.claimable_yield_fees_available() > 0, "there should be fees due to yield"
        #Lets withdraw 10% of traders funds...
        adaptervault.withdraw(trader_asset_bal_new // 10, trader, trader)
        print("GAS USED FOR PENDLE WITHDRAW = ", adaptervault._computation.net_gas_used) 
        assert (traderbal *9) //10 == pytest.approx(adaptervault.balanceOf(trader), rel=1e-2), "trader shares did not go down by 10%"

        #Get to  post maturity
        time_to_maturity = pendleMarket.expiry() - boa.env.evm.patch.timestamp
        if time_to_maturity > 0:
            boa.env.time_travel(seconds=time_to_maturity + 60)

        assert boa.env.evm.patch.timestamp > pendleMarket.expiry()
        print(adaptervault.totalAssets())
        pt_bal_pre = pt.balanceOf(adaptervault)
        asset_bal_pre = asset.balanceOf(adaptervault)
        trader_bal_pre = asset.balanceOf(trader)
        assert adaptervault.balanceOf(trader) == adaptervault.convertToShares( adaptervault.convertToAssets(adaptervault.balanceOf(trader)))
        # adaptervault.eval("self.vault_asset_balance_cache=0")
        # adaptervault.eval("self.total_asset_balance_cache=0")
        # adaptervault.eval("self.adapters_asset_balance_cache[" + pendle_adapter.address + "]=0")
        adaptervault.withdraw(
            adaptervault.convertToAssets(adaptervault.balanceOf(trader)),
            trader,
            trader
        )
        pt_bal_post = pt.balanceOf(adaptervault)
        asset_bal_post = asset.balanceOf(adaptervault)
        trader_bal_post = asset.balanceOf(trader)
        #The total PT burned should equal total stETH gained by both trader and vault
        pt_burned = pt_bal_pre - pt_bal_post
        print("pt_burned: ", pt_burned)
        trader_asset_gained = trader_bal_post - trader_bal_pre
        print("trader_asset_gained: ", trader_asset_gained)
        vault_asset_gained = asset_bal_post - asset_bal_pre
        print("vault_asset_gained: ", vault_asset_gained)
        print("total gained: ", trader_asset_gained + vault_asset_gained)
        #Theres always rounding issues somewhere...
        assert pt_burned == pytest.approx(trader_asset_gained + vault_asset_gained), "withdraw was not pegged"

        #Lets try a deposit, it all should goto cash
        asset.approve(adaptervault, 1*10**18)
        adaptervault.deposit(1*10**18, trader)
        assert asset.balanceOf(adaptervault) - asset_bal_post == pytest.approx(10**18), "asset not gained sufficiently"
        assert pt.balanceOf(adaptervault) - pt_bal_post == 0, "managed to deposit to PT post-maturity"



def test_markets_ena(setup_chain, trader, deployer, funds_alloc):
    #1. ENA on mainnet
    PENDLE_MARKET="0x9C73879F795CefA1D5239dE08d1B6Aba2D2d1434"
    ENA="0x57e114B691Db790C35207b2e685D4A43181e6061"
    PENDLE_PT="0x9946C55a34CD105f1e0CF815025EAEcff7356487"
    ena = _ena(trader, ENA)
    market_test(PENDLE_PT, ena, trader, deployer, PENDLE_MARKET, funds_alloc, PENDLE_ORACLE)

def test_markets_steth(setup_chain, trader, deployer, funds_alloc):
    #2. stETH on mainnet
    PENDLE_MARKET="0xd0354d4e7bcf345fb117cabe41acadb724eccca2" #Pendle: PT-stETH-26DEC24/SY-stETH Market Token
    STETH="0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
    PENDLE_PT="0x7758896b6AC966BbABcf143eFA963030f17D3EdF"
    steth = _steth(trader, STETH)
    market_test(PENDLE_PT, steth, trader, deployer, PENDLE_MARKET, funds_alloc, PENDLE_ORACLE)


