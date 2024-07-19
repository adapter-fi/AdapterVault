from web3 import Web3
import os, json, sys, datetime, math

if "__main__" in __name__:
    rpc = os.environ.get("RPC_URL")
    w3 = Web3(Web3.HTTPProvider(rpc))
    VAULT = sys.argv[1]
    GENESIS = 221750000 #Jun-14-2024 11:20:20 AM +UTC - prior to factory deployment
    with open("abis/AdapterVault.abi.json") as f:
        vault = w3.eth.contract(address=VAULT, abi=json.load(f))
    end = w3.eth.block_number
    start = int(GENESIS)
    CUT_OFF=1720656000 #UTC Thursday, 11 July 2024 00:00:00
    INCREMENT=400000
    balances = {}
    block_timestamp = {}
    for i in range(start, end, INCREMENT):
        for log in vault.events.Transfer().get_logs(fromBlock=i, toBlock=i+INCREMENT):
            print(log)
            if not log.blockNumber in block_timestamp:
                hdr = w3.eth.get_block(log.blockNumber)
                if hdr.timestamp > CUT_OFF:
                    break 
                block_timestamp[log.blockNumber] = hdr.timestamp
                print(datetime.datetime.fromtimestamp(hdr.timestamp))
            if log.args.receiver not in balances and log.args.receiver != "0x0000000000000000000000000000000000000000":
                balances[log.args.receiver] = []
            if log.args.sender not in balances and log.args.sender != "0x0000000000000000000000000000000000000000":
                balances[log.args.sender] = []
            if log.args.receiver != "0x0000000000000000000000000000000000000000":
                balances[log.args.receiver] += [{
                    "amount": log.args.value,
                    "timestamp": block_timestamp[log.blockNumber]
                }]
            if log.args.sender != "0x0000000000000000000000000000000000000000":
                balances[log.args.sender] += [{
                    "amount": log.args.value * -1,
                    "timestamp": block_timestamp[log.blockNumber]
                }]
    print(balances)
    #now summarize for each user..
    result = {}
    for user in balances:
        transfers = balances[user]
        shareHrs = 0
        for i, op in enumerate(transfers):
            if i == 0:
                #The first time... should be positive
                prevAmt = op["amount"]
                prevTs = op["timestamp"]
                assert prevAmt > 0, "not possible"
            else:
                #This is not the first, compute delta with previous...
                #Lets denominate this as share-hour
                delta = op["timestamp"] - prevTs
                deltaHrs = delta/3600
                if delta > 0:
                    #ignore share calculation if no time passed between transfers, but still account for the balance change
                    shareHrs += (prevAmt / deltaHrs)
                prevAmt = prevAmt + op["amount"]
                prevTs = op["timestamp"]
        #Finally compute until CUT_OFF
        delta = CUT_OFF - prevTs
        deltaHrs = delta/3600
        shareHrs += (prevAmt / deltaHrs)
        result[user] = int(math.floor(shareHrs))
        print(user, shareHrs)
    print(json.dumps(result, indent=2))
