import boa, os, json
from eth_account import Account
from decimal import Decimal

NOTHING="0x0000000000000000000000000000000000000000"


#---- chain specific stuff --- 
MULTISIG = "0x7B2cF15De19Ac87b50DDdA3Da7F2F300AE74B47f"
PENDLE_ROUTER="0x00000000005BBB0EF59571E58418F9a4357b68A0"
PENDLE_ROUTER_STATIC="0xAdB09F65bd90d19e3148D9ccb693F3161C6DB3E8"
PENDLE_ORACLE="0x1Fd95db7B7C0067De8D45C0cb35D59796adfD187"
#---- chain specific stuff --- 



#---- contracts deployed ----
PENDLE_ADAPTER_BLUEPRINT    = "0x7D87e88aA7000fe8c2C3B450844A2dc3A2312919" #Update here if deployed
ADAPTERVAULT_BLUEPRINT      = "0xe848ECE45a513b1bc4434c788f8b53DFF4E9BB20" #Update here if deployed
FUNDS_ALLOCATOR             = "0x1904163120C9345c1b41C520481CC677768E944d" #Update here if deployed
GOVERNANCE                  = "0xEdf4B1a86320a7b635F4a5E90044C928A16C781a" #Update here if deployed
PENDLE_FACTORY              = "0xcd3FF638DB6C1266b312B567DDE687C26A3314e5" #Update here if deployed
PT_MIGRATOR                 = "0xd8cF5dce611A34589E876dF9bF1A89a39e9E5187"
#---- contracts deployed ----

#------ vaults -----------
VAULT_EZETH = "0x1099ac45b80059733F719C7Dedf5a8ffCf02aAa8"
VAULT_RSETH = "0xe0229dcfa4d84998484a27ba01b4c2e78b1f02d3"
VAULT_WEETH = "0x10efb86d59eb8ae3d4a7966b4ab9ceb97e96d212"
#---------------------------


def generate(market, asset):
    rpc = os.environ.get("RPC_URL")
    assert rpc is not None and rpc != "", "RPC_URL MUST BE PROVIDED!!!"
    boa.set_network_env(rpc)
    private_key = os.environ.get("PRIVATE_KEY")
    assert private_key is not None and private_key != "", "PRIVATE_KEY MUST BE PROVIDED!!!"
    boa.env.add_account(Account.from_key(private_key))
    with open("contracts/vendor/IPMarketV3.json") as f:
        j = json.load(f)
        _market = boa.loads_abi(json.dumps(j["abi"]), name="IPMarketV3").at(market)
    sy, pt, yt = _market.readTokens()
    print(sy, pt, yt)
    pt = boa.load_partial("contracts/test_helpers/ERC20.vy").at(pt)

    pt_name = pt.name()
    pt_symbol = pt.symbol()
    decimals = pt.decimals()
    symbol = "a" + "-".join( pt_symbol.split("-")[:2])
    name = "Adapter " + " ".join(pt_name.split(" ")[:-1])
    print(name, symbol, decimals)
    _asset = boa.load_partial("contracts/test_helpers/ERC20.vy").at(asset)
    bal = _asset.balanceOf(MULTISIG)
    print(bal)
    factory = boa.load_partial("contracts/PendleVaultFactory.vy").at(PENDLE_FACTORY)
    args = [asset, market, name, symbol, decimals, Decimal(2.0), bal]
    print("args = ", args)
    print("0x" + factory.deploy_pendle_vault.prepare_calldata(asset, market, name, symbol, decimals, Decimal(2.0), bal).hex())


if "__main__" in __name__:
    rpc = os.environ.get("RPC_URL")
    assert rpc is not None and rpc != "", "RPC_URL MUST BE PROVIDED!!!"
    boa.set_network_env(rpc)
    private_key = os.environ.get("PRIVATE_KEY")
    assert private_key is not None and private_key != "", "PRIVATE_KEY MUST BE PROVIDED!!!"
    boa.env.add_account(Account.from_key(private_key))
    gas_price=boa.env.get_gas_price()
    if PENDLE_ADAPTER_BLUEPRINT == "":
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 1534994 * gas_price/10**18, " ETH")
        input("Going to deploy PendleAdapter blueprint (ctrl+c to abort, enter to continue)")
        pa = boa.load_partial("contracts/adapters/PendleAdapter.vy")
        pa.deploy_as_blueprint() #1,534,994
        exit()
    else:
        print("ADAPTERVAULT_BLUEPRINT already exists: ", PENDLE_ADAPTER_BLUEPRINT)
    if ADAPTERVAULT_BLUEPRINT == "":
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 5343449 * gas_price/10**18, " ETH")
        input("Going to deploy AdapterVault blueprint (ctrl+c to abort, enter to continue)")
        pa = boa.load_partial("contracts/AdapterVault.vy")
        pa.deploy_as_blueprint() #5,343,449
        exit()
    else:
        print("ADAPTERVAULT_BLUEPRINT already exists: ", ADAPTERVAULT_BLUEPRINT)
    if FUNDS_ALLOCATOR == "":
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 713222 * gas_price/10**18, " ETH")
        input("Going to deploy FundsAllocator (ctrl+c to abort, enter to continue)")
        pa = boa.load("contracts/FundsAllocator.vy") #713222
        print(pa) 
        exit()
    else:
        print("FUNDS_ALLOCATOR already exists: ", GOVERNANCE)
    if GOVERNANCE == "":
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 2846735 * gas_price/10**18, " ETH")
        input("Going to deploy Governance (ctrl+c to abort, enter to continue)")
        pa = boa.load("contracts/Governance.vy", MULTISIG, 60*60*24*30) #2846735
        print(pa) 
        exit()
    else:
        print("GOVERNANCE already exists: ", GOVERNANCE)
    if PENDLE_FACTORY == "":
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 896928 * gas_price/10**18, " ETH")
        input("Going to deploy PendleVaultFactory (ctrl+c to abort, enter to continue)")
        pa = boa.load("contracts/PendleVaultFactory.vy") #896928
        print(pa) 
        exit()
    else:
        print("PENDLE_FACTORY already exists: ", PENDLE_FACTORY)
    if PT_MIGRATOR == "":
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 896928 * gas_price/10**18, " ETH")
        input("Going to deploy PTMigrationRouter (ctrl+c to abort, enter to continue)")
        pa = boa.load("contracts/PTMigrationRouter.vy", PENDLE_ROUTER) #896928
        print(pa) 
        exit()
    else:
        print("PT_MIGRATOR already exists: ", PT_MIGRATOR)
    #Ensure all values for factory are correct... bottom-up, change owner last
    factory = boa.load_partial("contracts/PendleVaultFactory.vy").at(PENDLE_FACTORY)
    if factory.pendle_router() != PENDLE_ROUTER or factory.pendle_router_static() != PENDLE_ROUTER_STATIC or factory.pendle_oracle() != PENDLE_ORACLE:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 90807 * gas_price/10**18, " ETH")
        input("Going to deploy set pendle settings into factory (ctrl+c to abort, enter to continue)")
        factory.update_pendle_contracts(
            PENDLE_ROUTER,
            PENDLE_ROUTER_STATIC,
            PENDLE_ORACLE
        ) #90807
    if factory.governance_impl() != GOVERNANCE:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 45816 * gas_price/10**18, " ETH")
        input("Going to deploy set governance settings into factory (ctrl+c to abort, enter to continue)")
        factory.update_governance(GOVERNANCE) #45816
    if factory.funds_allocator_impl() != FUNDS_ALLOCATOR:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 45816 * gas_price/10**18, " ETH")
        input("Going to deploy set fundsallocator settings into factory (ctrl+c to abort, enter to continue)")
        factory.update_funds_allocator(FUNDS_ALLOCATOR) #45816
    if factory.adapter_vault_blueprint() != ADAPTERVAULT_BLUEPRINT or factory.pendle_adapter_blueprint() != PENDLE_ADAPTER_BLUEPRINT:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 68330 * gas_price/10**18, " ETH")
        input("Going to deploy set blueprint into factory (ctrl+c to abort, enter to continue)")
        factory.update_blueprints(ADAPTERVAULT_BLUEPRINT, PENDLE_ADAPTER_BLUEPRINT) #68330


    if factory.owner() != MULTISIG:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 28269 * gas_price/10**18, " ETH")
        input("Going to change owner of factory (ctrl+c to abort, enter to continue)")
        factory.replace_owner(MULTISIG) #28269
