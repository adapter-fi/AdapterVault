import deploy_arbitrum
import deploy_mainnet
from deploy_adapter import pendle_Market
import sys
import boa, os, json
from eth_account import Account
from decimal import Decimal
from web3 import Web3
import eth_abi


def json_abi(addr, fname, name="whatever"):
    with open(fname) as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name=name)
    return factory.at(addr)

def sy_token(_sy):
    return json_abi(_sy, "contracts/vendor/IStandardizedYield.json", name="IStandardizedYield")


if "__main__" in __name__:
    net = sys.argv[1]
    VAULT = sys.argv[2]
    MARKET_OLD = sys.argv[3]
    MARKET_NEW = sys.argv[4]
    print(net, VAULT)
    rpc = os.environ.get("RPC_URL")
    w3 = Web3(Web3.HTTPProvider(rpc))
    cid = w3.eth.chain_id
    if net == "arbitrum":
        assert cid == 42161, "not on correct RPC"
        PENDLE_ROUTER = deploy_arbitrum.PENDLE_ROUTER
        PENDLE_ROUTER_STATIC = deploy_arbitrum.PENDLE_ROUTER_STATIC
        PENDLE_ORACLE = deploy_arbitrum.PENDLE_ORACLE        
    elif net == "mainnet":
        assert cid == 1, "not on correct RPC"
        PENDLE_ROUTER = deploy_mainnet.PENDLE_ROUTER
        PENDLE_ROUTER_STATIC = deploy_mainnet.PENDLE_ROUTER_STATIC
        PENDLE_ORACLE = deploy_mainnet.PENDLE_ORACLE
    else:
        raise Exception("network not implemented")
    boa.set_network_env(rpc)
    private_key = os.environ.get("PRIVATE_KEY")
    assert private_key is not None and private_key != "", "PRIVATE_KEY MUST BE PROVIDED!!!"
    boa.env.add_account(Account.from_key(private_key))

    market_old = pendle_Market(MARKET_OLD)
    market_new = pendle_Market(MARKET_NEW)
    vault = boa.load_partial("contracts/AdapterVault.vy").at(VAULT)
    ASSET = vault.asset()
    SY_OLD, PT_OLD, _ = market_old.readTokens()
    SY_NEW, PT_NEW, _ = market_new.readTokens()
    assert SY_OLD==SY_NEW, "we should be dealing with same SY!!!"

    pt_old = boa.load_partial("contracts/test_helpers/ERC20.vy").at(PT_OLD)
    pt_new = boa.load_partial("contracts/test_helpers/ERC20.vy").at(PT_NEW)
    asset = boa.load_partial("contracts/test_helpers/ERC20.vy").at(ASSET)

    sy = sy_token(SY_OLD)

    _, UNDERLYING, DECIMALS = sy.assetInfo()
    # print(UNDERLYING, DECIMALS)
    UNDERLYING_SYMBOL = boa.load_partial("contracts/test_helpers/ERC20.vy").at(UNDERLYING).symbol()

    #Find amounts, as underlying asset
    pt_old_pre = pt_old.balanceOf(vault)
    asset_pre = asset.balanceOf(vault)

    # #assuming 1:1 during maturity...
    pt_old_pre_underlying = pt_old_pre
    asset_pre_underlying = sy.previewDeposit(ASSET, asset_pre)
    router_static = json_abi(PENDLE_ROUTER_STATIC, "contracts/vendor/IPRouterStatic.json", name="IPRouterStatic")


    print("currently in mature adapter  : ", pt_old_pre_underlying / 10**DECIMALS , " ", UNDERLYING_SYMBOL)
    print("currently in cash            : ", asset_pre_underlying / 10**DECIMALS , " ", UNDERLYING_SYMBOL)
    print("TOTAL                        : ", (pt_old_pre_underlying / 10**DECIMALS) + (asset_pre_underlying / 10**DECIMALS), " ", UNDERLYING_SYMBOL)

    print("======== Doing nothing, funds at next maturity will be ==============")

    print("mature adapter  : ", pt_old_pre_underlying / 10**DECIMALS , " ", UNDERLYING_SYMBOL)
    print("cash            : ", asset_pre_underlying / 10**DECIMALS , " ", UNDERLYING_SYMBOL, " + additional underlying yield from asset token")
    print("TOTAL           : ", (pt_old_pre_underlying / 10**DECIMALS) + (asset_pre_underlying / 10**DECIMALS), " ", UNDERLYING_SYMBOL , " plus some yield from cash")


    print("======== mature --> cash, funds at next maturity will be ==============")

    print("mature adapter  : 0 ", UNDERLYING_SYMBOL)
    #perform full withdrawal... 
    #pegged at maturity...
    asset_amt = sy.previewRedeem(ASSET, pt_old_pre_underlying)
    total_asset_post_withdraw = asset_amt + asset_pre

    print("cash            : ", sy.previewDeposit(ASSET, total_asset_post_withdraw) / 10**DECIMALS , " ", UNDERLYING_SYMBOL, " + additional underlying yield from asset token")
    print("TOTAL           : ", sy.previewDeposit(ASSET, total_asset_post_withdraw) / 10**DECIMALS , " ", UNDERLYING_SYMBOL, " + additional underlying yield from asset token, more than previous option")


    print("======== mature+ cash --> new adapter, funds at next maturity will be ==============")

    print("mature adapter   : 0 ", UNDERLYING_SYMBOL)
    print("cash             : 0 ", UNDERLYING_SYMBOL)

    #compute total_asset_post_withdraw asset  to PT (PS: we ignore mint method for now)
    pt_out, _, _, _, _ = router_static.swapExactTokenForPtStatic(MARKET_NEW, ASSET, total_asset_post_withdraw)
    #compute post maturity sy amount, 1 PT = 1 SY
    sy_out = pt_out
    #and we assume 1 sy = 1 underlying...

    print("new adapter      : ", sy_out / 10**DECIMALS , " ", UNDERLYING_SYMBOL)
    print("TOTAL            : ", sy_out / 10**DECIMALS , " ", UNDERLYING_SYMBOL)
