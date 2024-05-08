import requests, json, os, sys
from web3 import Web3


MARKET=sys.argv[1]
PENDLE_ORACLE="0x66a1096C6366b2529274dF4f5D8247827fe4CEA8"
PENDLE_ROUTER_STATIC="0x263833d47eA3fA4a30f269323aba6a107f9eB14C"

if "__main__" in __name__:
    w3 = Web3(Web3.HTTPProvider('https://eth-mainnet.g.alchemy.com/v2/' + os.getenv("WEB3_ALCHEMY_API_KEY")))
    assert w3.is_connected() == True, "web3 must be connected"

    blocks = []
    for log in w3.eth.get_logs({"address": MARKET, 'fromBlock': 0, 'toBlock': "latest"}):
        if log.blockNumber not in blocks:
            if log.blockNumber > 17449767:
                # ^ this is block number from when router static got getPtToAssetRate function
                blocks += [log.blockNumber]
    blocks.sort()
    with open("contracts/vendor/IPRouterStatic.json") as f:
        abi = json.load(f)["abi"]
    st = w3.eth.contract(abi=abi, address=PENDLE_ROUTER_STATIC)
    print("block_number, block_timestamp, spotpt2asset")
    for blk in blocks:
        price = (st.functions.getPtToAssetRate(MARKET).call(block_identifier=blk) * 1.0) / 10**18
        block = w3.eth.get_block(blk)
        print("%d, %d, %.18f" %( blk, block.timestamp, price))
    
