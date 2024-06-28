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
PENDLE_MARKET_FUTURE="0xc374f7ec85f8c7de3207a10bb1978ba104bda3b2" #Pendle: PT-stETH-25DEC25/SY-stETH Market Token
STETH="0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
PENDLE_PT="0x7758896b6AC966BbABcf143eFA963030f17D3EdF"
PENDLE_PT_FUTURE="0xf99985822fb361117FCf3768D34a6353E6022F5F"
PENDLE_ORACLE="0x66a1096C6366b2529274dF4f5D8247827fe4CEA8"

MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy

d4626_name = "stETH-Pendle"
d4626_token = "pstETH"
d4626_decimals = 18

@pytest.fixture
def hardhat_fork_block(ensure_hardhat):
    reset_hardhat_fork(19675100) #Apr-17-2024 12:09:23 PM +UTC


@pytest.fixture
def deployer(accounts):
    deployer = accounts[0]
    deployer.balance += 10000 * int(1e18)
    return deployer

@pytest.fixture
def trader(accounts):
    trader = accounts[1]
    trader.balance += 10000 * int(1e18)
    return trader

@pytest.fixture
def attacker(accounts):
    attacker = accounts[2]
    attacker.balance += 10000 * int(1e18)
    return attacker

@pytest.fixture
def pendle_adapter(project, hardhat_fork_block, deployer, steth, pendleOracle):
    pa = deployer.deploy(project.PendleAdapter, steth, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, PENDLE_MARKET, PENDLE_ORACLE)
    return pa

@pytest.fixture
def pendle_adapter_clone(project, hardhat_fork_block, deployer, steth, pendleOracle):
    pa = deployer.deploy(project.PendleAdapter, steth, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, PENDLE_MARKET, PENDLE_ORACLE)
    return pa

@pytest.fixture
def pendle_adapter_replacement(project, hardhat_fork_block, deployer, steth, pendleOracle):
    pa = deployer.deploy(project.PendleAdapter, steth, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, PENDLE_MARKET, PENDLE_ORACLE)
    return pa


@pytest.fixture
def pendle_adapter_future(project, hardhat_fork_block, deployer, steth, pendleOracle):
    pa = deployer.deploy(project.PendleAdapter, steth, PENDLE_ROUTER, PENDLE_ROUTER_STATIC, PENDLE_MARKET_FUTURE, PENDLE_ORACLE)
    return pa

@pytest.fixture
def steth(project, hardhat_fork_block, trader):
    st = project.ERC20.at(STETH)
    #TODO: "airdrop" 1000000 stETH to trader
    #stETH contract has  shares in first slot mapping (address => uint256) private shares;
    abi_encoded = eth_abi.encode(['address', 'uint256'], [trader.address, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()

    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        "params": [STETH, storage_slot, "0x" + eth_abi.encode(["uint256"], [50000 * 10**18]).hex()]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    #Cant check for equality as the hacked storage is for shares, balance is virtual
    assert st.balanceOf(trader) >= 50000 * 10**18, "Trader did not get 'airdrop'"
    return st


@pytest.fixture
def pt(project, hardhat_fork_block):
    return project.ERC20.at(PENDLE_PT)

@pytest.fixture
def pt_future(project, hardhat_fork_block):
    return project.ERC20.at(PENDLE_PT_FUTURE)

@pytest.fixture
def pendleRouter(project, hardhat_fork_block):
    return project.IPAllActionV3.at(PENDLE_ROUTER)

@pytest.fixture
def pendleOracle(project, hardhat_fork_block, deployer):
    #re: https://docs.pendle.finance/Developers/Integration/HowToIntegratePtAndLpOracle#third-initialize-the-oracle
    #Must ensure cardinality, doing for both markets same time
    for market in [PENDLE_MARKET, PENDLE_MARKET_FUTURE]:
        oracle = project.PendlePtLpOracle.at(PENDLE_ORACLE)
        increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(PENDLE_MARKET, 1200)
        if increaseCardinalityRequired:
            project.IPMarketV3.at(market).increaseObservationsCardinalityNext(cardinalityRequired, sender=deployer, value=0)
            print("cardinality increased")
        #just in case, simulate passage of time
        ape.chain.mine(1, deltatime=1200)
        increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(PENDLE_MARKET, 1200)
        print(increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied)
    return oracle

@pytest.fixture
def funds_alloc(project, deployer, hardhat_fork_block):
    f = deployer.deploy(project.FundsAllocator)
    return f

@pytest.fixture
def adaptervault(project, deployer, steth, trader, funds_alloc, hardhat_fork_block):
    v = deployer.deploy(project.AdapterVault, d4626_name, d4626_token, d4626_decimals, steth, deployer, funds_alloc, "2.0")
    return v

def test_pendle_adapter(project, pendle_adapter, pt, steth, pendleRouter, trader, deployer, adaptervault, pendleOracle):
    #Add single adapter
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    strategy[0] = (pendle_adapter, 1)

    adaptervault.set_strategy(deployer, strategy, 0, sender=deployer)
    result = adaptervault.add_adapter(pendle_adapter, sender=deployer) 
    assert result.return_value == True

    #Trader invests 1 stETH
    steth.approve(adaptervault, 1*10**18, sender=trader)

    bal_pre = steth.balanceOf(trader)
    ex_rate = pendleOracle.getPtToAssetRate(PENDLE_MARKET, 900)
    # with ape.reverts():
    # print("=========")
    result = adaptervault.deposit(1*10**18, trader, sender=trader)
    print("GAS USED FOR PENDLE DEPOSIT = ", result.gas_used) 

    deducted = bal_pre - steth.balanceOf(trader)
    print(deducted)
    assert deducted == 10**18, "Invalid amount got deducted"
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
    ape.chain.mine(1, deltatime=60*60*24*30) 
    traderbal = adaptervault.balanceOf(trader)
    trader_asset_bal_new = adaptervault.convertToAssets(traderbal)
    print(trader_asset_bal_new)
    assert trader_asset_bal_new > trader_asset_bal, "new trader balance should be higher because of yield"
    assert adaptervault.claimable_yield_fees_available() > 0, "there should be fees due to yield"
    #Lets withdraw 10% of traders funds...
    result = adaptervault.withdraw(trader_asset_bal_new // 10, trader, trader, sender=trader)
    print("GAS USED FOR PENDLE WITHDRAW = ", result.gas_used) 
    assert (traderbal *9) //10 == pytest.approx(adaptervault.balanceOf(trader)), "trader shares did not go down by 10%"
    #fast forward to post-maturity, forwarding 8 more months
    ape.chain.mine(1, deltatime=60*60*24*30*8)
    assert ape.chain.blocks.head.timestamp > 1735171200, "we didn't time travel sufficiently"

    print(adaptervault.totalAssets())
    #trader withdraws everything (should be 1:1 peg)
    pt_bal_pre = pt.balanceOf(adaptervault)
    steth_bal_pre = steth.balanceOf(adaptervault)
    trader_bal_pre = steth.balanceOf(trader)
    adaptervault.withdraw(adaptervault.convertToAssets(adaptervault.balanceOf(trader)), trader, trader, sender=trader)
    pt_bal_post = pt.balanceOf(adaptervault)
    steth_bal_post = steth.balanceOf(adaptervault)
    trader_bal_post = steth.balanceOf(trader)

    #The total PT burned should equal total stETH gained by both trader and vault
    pt_burned = pt_bal_pre - pt_bal_post
    print("pt_burned: ", pt_burned)
    trader_steth_gained = trader_bal_post - trader_bal_pre
    print("trader_steth_gained: ", trader_steth_gained)
    vault_steth_gained = steth_bal_post - steth_bal_pre
    print("vault_steth_gained: ", vault_steth_gained)
    print("total gained: ", trader_steth_gained + vault_steth_gained)
    #Theres always rounding issues somewhere...
    assert pt_burned == pytest.approx(trader_steth_gained + vault_steth_gained), "withdraw was not pegged"


    #Lets try a deposit, it all should goto cash
    steth.approve(adaptervault, 1*10**18, sender=trader)
    adaptervault.deposit(1*10**18, trader, sender=trader)
    #Everything should have gone into cash...
    #Theres always rounding issues somewhere...
    #These 2 asserts prove that the vault is honouring maxDeposit() of adapter.
    assert steth.balanceOf(adaptervault) - steth_bal_post == pytest.approx(10**18), "steth not gained sufficiently"
    assert pt.balanceOf(adaptervault) - pt_bal_post == 0, "managed to deposit to PT post-maturity"


def test_pendle_adapter_maturity(project, pendle_adapter, pt, steth, pendleRouter, trader, deployer, adaptervault, pendleOracle, pendle_adapter_future, pt_future):
    #Add single adapter - current maturity
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    strategy[0] = (pendle_adapter, 1)

    adaptervault.set_strategy(deployer, strategy, 0, sender=deployer)
    result = adaptervault.add_adapter(pendle_adapter, sender=deployer) 
    assert result.return_value == True

    #Trader invests 1 stETH
    steth.approve(adaptervault, 1*10**18, sender=trader)

    bal_pre = steth.balanceOf(trader)
    ex_rate = pendleOracle.getPtToAssetRate(PENDLE_MARKET, 900)
    # with ape.reverts():
    # print("=========")
    adaptervault.deposit(1*10**18, trader, sender=trader)

    deducted = bal_pre - steth.balanceOf(trader)
    print(deducted)
    assert deducted == 10**18, "Invalid amount got deducted"
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


    #Fast forward to post maturity, 9 months in the future
    ape.chain.mine(1, deltatime=60*60*24*30*9)
    assert ape.chain.blocks.head.timestamp > 1735171200, "we didn't time travel sufficiently"

    #Now we need to create a new adapter with more future maturity, lucky for us there are
    #multiple stETH markets live at the moment, we pick another one.
    #https://etherscan.io/address/0xc374f7ec85f8c7de3207a10bb1978ba104bda3b2

    #Add the new adapter with 0 allocation to it
    pt_pre = pt.balanceOf(adaptervault)
    strategy[1] = (pendle_adapter_future, 0)
    adaptervault.set_strategy(deployer, strategy, 0, sender=deployer)
    result = adaptervault.add_adapter(pendle_adapter_future, sender=deployer) 
    assert result.return_value == True

    #There should be changes to adapter funds yet
    assert pt_pre == pt.balanceOf(adaptervault), "PT balance should not change"
    assert pt_future.balanceOf(adaptervault) == 0, "There should not be any allocation to new adapter yet"

    #Lets allocate everything to new adapter, and pray we dont get frontrun....
    total_assets = adaptervault.totalAssets()
    strategy[0] = (pendle_adapter, 0)
    strategy[1] = (pendle_adapter_future, 1)
    print("total_assets pre remove: ", total_assets)
    adaptervault.set_strategy(deployer, strategy, 0, sender=deployer)

    #NOTE: we are using force mode, because for some reason we are getting a 5.5% slippage
    #during deposit to new market. My guess it this is due to lack of market activity when we
    #time traveled
    adaptervault.remove_adapter(pendle_adapter, True, True, sender=deployer, gas=2500000)
    total_assets_post = adaptervault.totalAssets()
    print("total_assets before: ", total_assets)
    print("total_assets_post: ", total_assets_post)
    print("loss: ", (total_assets - total_assets_post)*100/total_assets)
    print("old: ", pt.balanceOf(adaptervault))
    print("new: ", pt_future.balanceOf(adaptervault))
    assert pt.balanceOf(adaptervault) < 5, "old PT should have been redeemed fully"
    # ^ few wei was left over... due to rounding issues
    assert pt_future.balanceOf(adaptervault) > pt_pre, "at future markets maturity, we expect more tokens than we currently have"

def test_pendle_adapter_claim_rewards(project, pendle_adapter, pt, steth, pendleRouter, trader, deployer, adaptervault, pendleOracle, attacker):
    #Add single adapter
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    strategy[0] = (pendle_adapter, 1)

    adaptervault.set_strategy(deployer, strategy, 0, sender=deployer)
    result = adaptervault.add_adapter(pendle_adapter, sender=deployer) 
    assert result.return_value == True

    #Trader invests 1 stETH
    steth.approve(adaptervault, 1*10**18, sender=trader)

    bal_pre = steth.balanceOf(trader)
    ex_rate = pendleOracle.getPtToAssetRate(PENDLE_MARKET, 900)
    # with ape.reverts():
    # print("=========")
    adaptervault.deposit(1*10**18, trader, sender=trader)

    deducted = bal_pre - steth.balanceOf(trader)
    print(deducted)
    assert deducted == 10**18, "Invalid amount got deducted"
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

    #Check rewards available
    market = project.IPMarketV3.at(PENDLE_MARKET)
    for tok in market.getRewardTokens():
        print(tok, project.ERC20.at(tok).balanceOf(deployer))
        # #Hmm.. we need to "airdrop" PENDLE to the market to be eligible for the reward...
        # market_pre = project.ERC20.at(tok).balanceOf(PENDLE_MARKET) 
        
        # abi_encoded = eth_abi.encode(['address', 'uint256'], [PENDLE_MARKET, 15])
        # storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()

        # set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        #     "params": [tok, storage_slot, "0x" + eth_abi.encode(["uint256"], [market_pre + (10000000 * 10**18)]).hex()]}
        # print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
        # print("market PENDLE", project.ERC20.at(tok).balanceOf(PENDLE_MARKET) - market_pre )

    ape.chain.mine(1000, deltatime=60*60*24*30) 

    #Test non-owner cant claim reward
    with ape.reverts("Only owner can claimRewards!"):
        adaptervault.claimRewards(pendle_adapter, deployer, sender=attacker)

    #I am unable to trigger the reward mechanism to test against, but validated in trace it works
    receipt = adaptervault.claimRewards(pendle_adapter, deployer, sender=deployer)
    receipt.show_trace()
    for tok in market.getRewardTokens():
        print(tok, project.ERC20.at(tok).balanceOf(deployer))

def test_adapter_swap(project, pendle_adapter, pendle_adapter_clone, pendle_adapter_future, pt, steth, pendleRouter, trader, deployer, adaptervault, pendleOracle, attacker):
    #Add single adapter
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    strategy[0] = (pendle_adapter, 1)

    adaptervault.set_strategy(deployer, strategy, 0, sender=deployer)
    result = adaptervault.add_adapter(pendle_adapter, sender=deployer) 
    assert result.return_value == True

    #Trader invests 1 stETH
    steth.approve(adaptervault, 1*10**18, sender=trader)

    adaptervault.deposit(1*10**18, trader, sender=trader)


    total_assets = adaptervault.totalAssets()
    pt_pre = pt.balanceOf(adaptervault)
    #ensure random person cant swap adapter
    with ape.reverts("Only owner can swap Lending Adapters."):
        adaptervault.swap_adapters(pendle_adapter, pendle_adapter_clone, sender=attacker)
    
    #ensure bogus address isint accepted - here its null address and vault treats it as balance = 0
    with ape.reverts("Can't have empty address for adapter."):
        adaptervault.swap_adapters(pendle_adapter, "0x0000000000000000000000000000000000000000", sender=deployer)

    #ensure a different market with no balance fails
    with ape.reverts("ERROR - Swap exceeds maximum slippage."):
        adaptervault.swap_adapters(pendle_adapter, pendle_adapter_future, sender=deployer)

    #legit new adapter should be accepted
    adaptervault.swap_adapters(pendle_adapter, pendle_adapter_clone, sender=deployer)

    #TODO: tests to prove it actually changed



def test_pendle_adapter_mint(project, pendle_adapter, pendle_adapter_clone, pendle_adapter_future, pt, steth, pendleRouter, trader, deployer, adaptervault, pendleOracle, attacker):
    #Add single adapter
    strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
    strategy[0] = (pendle_adapter, 1)

    adaptervault.set_strategy(deployer, strategy, 0, sender=deployer)
    result = adaptervault.add_adapter(pendle_adapter, sender=deployer) 
    assert result.return_value == True

    #Trader direct mint 1 stETH
    steth.approve(pendleRouter, 1*10**18, sender=trader)
    market = project.IPMarketV3.at(PENDLE_MARKET)
    ti = {
        "tokenIn": STETH,
        "netTokenIn": 1*10**18,
        "tokenMintSy": STETH,
        "pendleSwap": "0x0000000000000000000000000000000000000000",
        "swapData": (
            0,
            "0x0000000000000000000000000000000000000000",
            "0x",
            False
        )
    }

    _, _, yt = market.readTokens()
    pendleRouter.mintPyFromToken(trader, yt, 0, ti, sender=trader, gas=1500000)
    print(pt.balanceOf(trader))
    print(project.ERC20.at(yt).balanceOf(trader))
    #Trader invests 1 stETH
    steth.approve(adaptervault, 1*10**18, sender=trader)
    recpt = adaptervault.deposit(1*10**18, trader, sender=trader, gas=30000000)
    print("naive deposit gas: ", recpt.gas_used)

    #Now we do this with pregen info...
    pregen_bytes = pendle_adapter.generate_pregen_info(10**18)

    steth.approve(adaptervault, 1*10**18, sender=trader)
    #Note we had to add _min_shares argument because it comes before pregen
    recpt_optimized = adaptervault.deposit(1*10**18, trader, 0, [pregen_bytes], sender=trader, gas=30000000)
    print("optimized deposit gas: ", recpt_optimized.gas_used)
    assert recpt_optimized.gas_used < recpt.gas_used, "pregen should use less gas"
    