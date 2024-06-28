import deploy_arbitrum
import deploy_mainnet
import sys
import boa, os, json
from eth_account import Account
from decimal import Decimal
from web3 import Web3
import eth_abi


def pendle_Market(_pendle_market):
    with open("contracts/vendor/IPMarketV3.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="IPMarketV3")
    return factory.at(_pendle_market)


if "__main__" in __name__:
    net = sys.argv[1]
    ASSET = sys.argv[2]
    MARKET = sys.argv[3]
    print(net, ASSET, MARKET)
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
    assert rpc is not None and rpc != "", "RPC_URL MUST BE PROVIDED!!!"
    boa.set_network_env(rpc)
    private_key = os.environ.get("PRIVATE_KEY")
    assert private_key is not None and private_key != "", "PRIVATE_KEY MUST BE PROVIDED!!!"
    boa.env.add_account(Account.from_key(private_key))
    gas_price=boa.env.get_gas_price()

    market = pendle_Market(MARKET)
    #Check the oracle
    with open("contracts/vendor/PendlePtLpOracle.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="PendlePtLpOracle")
    oracle = factory.at(PENDLE_ORACLE)
    increaseCardinalityRequired, cardinalityRequired, oldestObservationSatisfied = oracle.getOracleState(MARKET, 1200)
    if increaseCardinalityRequired:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        input("Going to update TWAP (ctrl+c to abort, enter to continue)")
        market.increaseObservationsCardinalityNext(cardinalityRequired)
        os.exit()

    if not oldestObservationSatisfied:
        raise Exception("Please wait a bit..")

    print("estimated gas price is: ", gas_price/10**9, " gwei")
    input("Going to deploy adapter (ctrl+c to abort, enter to continue)")
    adapter = boa.load(
        "contracts/adapters/PendleAdapter.vy",
        ASSET,
        PENDLE_ROUTER,
        PENDLE_ROUTER_STATIC,
        MARKET,
        PENDLE_ORACLE
    )
    print(adapter)


    init_args = eth_abi.encode(['address' , "address", "address", "address", "address"], [
        ASSET,
        PENDLE_ROUTER,
        PENDLE_ROUTER_STATIC,
        MARKET,
        PENDLE_ORACLE
      ]).hex()


    print("init args for verification: ", init_args)
