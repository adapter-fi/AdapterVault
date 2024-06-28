import pytest
import pprint
import ape
from tests.conftest import ensure_hardhat, reset_hardhat_fork
from web3 import Web3
import requests, json
import eth_abi

PENDLE_ROUTER="0x00000000005BBB0EF59571E58418F9a4357b68A0"
PENDLE_ROUTER_STATIC="0x263833d47eA3fA4a30f269323aba6a107f9eB14C"
PENDLE_MARKET="0xd0354d4e7bcf345fb117cabe41acadb724eccca2" #Pendle: PT-stETH-26DEC24/SY-stETH Market Token
STETH="0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
PENDLE_PT="0x7758896b6AC966BbABcf143eFA963030f17D3EdF"
PENDLE_ORACLE="0x66a1096C6366b2529274dF4f5D8247827fe4CEA8"

MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935

@pytest.fixture
def hardhat_fork_block(ensure_hardhat):
    reset_hardhat_fork(19675100) #Apr-17-2024 12:09:23 PM +UTC


@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def pendle_adapter(project, hardhat_fork_block, deployer, steth, pendleOracle):
    pa = deployer.deploy(project.PendleAdapter, steth, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, PENDLE_MARKET, PENDLE_ORACLE)
    return pa

@pytest.fixture
def steth(project, hardhat_fork_block, trader):
    st = project.ERC20.at(STETH)
    #TODO: "airdrop" 1000000 stETH to trader
    #stETH contract has  shares in first slot mapping (address => uint256) private shares;
    abi_encoded = eth_abi.encode(['address', 'uint256'], [trader.address, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()

    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        "params": [STETH, storage_slot, "0x" + eth_abi.encode(["uint256"], [5000 * 10**18]).hex()]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    #Cant check for equality as the hacked storage is for shares, balance is virtual
    assert st.balanceOf(trader) > 5000 * 10**18, "Trader did not get 'airdrop'"
    return st


@pytest.fixture
def pt(project, hardhat_fork_block):
    return project.ERC20.at(PENDLE_PT)

@pytest.fixture
def pendleRouter(project, hardhat_fork_block):
    return project.IPAllActionV3.at(PENDLE_ROUTER)

@pytest.fixture
def pendleOracle(project, hardhat_fork_block, deployer):
    #re: https://docs.pendle.finance/Developers/Integration/HowToIntegratePtAndLpOracle#third-initialize-the-oracle
    #Must ensure cardinality
    oracle = project.PendlePtLpOracle.at(PENDLE_ORACLE)
    increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(PENDLE_MARKET, 1200)
    if increaseCardinalityRequired:
        project.IPMarketV3.at(PENDLE_MARKET).increaseObservationsCardinalityNext(cardinalityRequired, sender=deployer)
        print("cardinality increased")
    #just in case, simulate passage of time
    ape.chain.mine(1, deltatime=1200)
    increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(PENDLE_MARKET, 900)
    print(increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied)
    return oracle

def test_pendle_adapter_standalone(project, pendle_adapter, pt, steth, pendleRouter, trader, pendleOracle):
    #Dont have any state...
    #we use sender=aave_adapter in view functions to troll the vault_location() method
    assert pendle_adapter.totalAssets(sender=pendle_adapter) == 0, "Asset balance should be 0"
    assert pendle_adapter.maxWithdraw(sender=pendle_adapter) == 0, "maxWithdraw should be 0"
    assert pendle_adapter.maxDeposit(sender=pendle_adapter) > 0, "maxDeposit should > 0"
    assert pt.balanceOf(pendle_adapter) == 0, "PT balance incorrect"
    #View functions can be tested without a vault because of msg.sender detection in adapter
    #Trader buys 100 stETH worth of PT directly from pendle
    steth.approve(pendleRouter, 100*10**18, sender=trader)

    ap = {
        "guessMin": 0,
        "guessMax": MAX_UINT256,
        "guessOffchain": 0,
        "maxIteration": 256,
        "eps": 10**14
    }
    ti = {
        "tokenIn": STETH,
        "netTokenIn": 100*10**18,
        "tokenMintSy": STETH,
        "pendleSwap": "0x0000000000000000000000000000000000000000",
        "swapData": (
            0,
            "0x0000000000000000000000000000000000000000",
            "0x",
            False
        )
    }
    limit = {
        "limitRouter": "0x0000000000000000000000000000000000000000",
        "epsSkipMarket": 0,
        "normalFills": [],
        "flashFills": [],
        "optData": "0x"
    }
    print(ape.chain.blocks.head.timestamp)

    recpt = pendleRouter.swapExactTokenForPt(trader, PENDLE_MARKET, 0, ap, ti, limit, sender=trader)
    # recpt.show_trace()
    pt_bal = pt.balanceOf(trader)
    assert pt_bal > 100*10**18, "did not get enough PT"
    print("pt_bal", pt_bal)

    oracle_price = pendleOracle.getPtToAssetRate(PENDLE_MARKET, 900)
    total_assets = pendle_adapter.totalAssets(sender=trader)

    assert total_assets == pytest.approx( (pt_bal * oracle_price) // 10**18), "total_assets incorrect"
    assert total_assets < 100*10**18, "total_assets should be less than 100 stETH, due to slippage"
    print(total_assets / 10**18)
        
    assert pendle_adapter.maxWithdraw(sender=trader) == total_assets, "max withdraw must equal total assets"
    assert pendle_adapter.maxDeposit(sender=trader) == MAX_UINT256, "max deposit should be unlimited"

    #Simulate passage of time until maturity
    #expiry of our test contract is 1735171200 - 26 December 2024
    #our fork starts at 17 April 2024
    #Let's forward 9 months into the future, this would be sometime in January 2025
    #forwarding 900 seconds per block, 25920 blocks (60*60*24*30*9/900)
    # set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_mine", "id": 1,
    #     "params": ["0x6540", "0x384"]} 
    # print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    ape.chain.mine(1, deltatime=60*60*24*30*9)
    assert ape.chain.blocks.head.timestamp > 1735171200, "we didn't time travel sufficiently"
    
    assert pendle_adapter.maxDeposit(sender=trader) == 0, "max deposit should be 0 post-maturity"

    total_assets = pendle_adapter.totalAssets(sender=trader)
    pt_bal = pt.balanceOf(trader)

    assert total_assets == pytest.approx(pt_bal), "PT should be pegged to asset post-maturity"
    assert pendle_adapter.maxWithdraw(sender=trader) == total_assets, "max withdraw must equal total assets"


def test_pendle_adapter_mint(project, pendle_adapter,  pt, steth, pendleRouter, trader):

    #Trader direct mint 1 stETH
    steth.transfer(pendle_adapter, 1*10**18, sender=trader)
    ret = pendle_adapter.deposit(1*10**18, sender=trader, gas=3000000)
    print("no pregen", ret.gas_used)

    #Compute pregen
    pregen_bytes = pendle_adapter.generate_pregen_info(10**18)
    steth.transfer(pendle_adapter, 1*10**18, sender=trader)
    ret = pendle_adapter.deposit(1*10**18, pregen_bytes, sender=trader, gas=3000000)
    print("pregen", ret.gas_used)



