import boa, os, json
from decimal import Decimal
from eth_account import Account

MULTISIG = "0x5287218b3E9B3b9D394e0A0656eD256fAfFd333a"
PENDLE_ROUTER="0x00000000005BBB0EF59571E58418F9a4357b68A0"
NOTHING="0x0000000000000000000000000000000000000000"
PENDLE_ROUTER_STATIC="0x263833d47eA3fA4a30f269323aba6a107f9eB14C"
PENDLE_ORACLE="0x66a1096C6366b2529274dF4f5D8247827fe4CEA8"


#---- contracts deployed ----
PENDLE_ADAPTER_BLUEPRINT    = "0xF32302F640342Ce10ECfbaD830251588518A63A6" #Update here if deployed
ADAPTERVAULT_BLUEPRINT      = "0x8ccE1007C90E648BD54Fa4d6b284Bb002F69dECd" #Update here if deployed
FUNDS_ALLOCATOR             = "0x1904163120C9345c1b41C520481CC677768E944d" #Update here if deployed
GOVERNANCE                  = "0xEdf4B1a86320a7b635F4a5E90044C928A16C781a" #Update here if deployed
PENDLE_FACTORY              = "0xcd3FF638DB6C1266b312B567DDE687C26A3314e5" #Update here if deployed
PT_MIGRATOR                 = "0x33376eE814558e305c6279C66117499757C6F92f"

#------ vaults -----------
VAULT_RSETH = "0x9A7b4dDA01F1580CD8e4E4849A3532C34a4C4081"
VAULT_RSWETH = "0xe6cD0b7800cA3e297b8fBd7697Df9E9F6A27f0F5"
VAULT_EETH = "0x521362A7C33107cCAAd13274e9BD7D7B7EC48375"
VAULT_EZETH = "0x945f0cf0DDb3A20a4737d3e1f3cA43DE9C185440"
VAULT_USDE = "0x02593d7Af1A77e3b2e3FDac9601a28169bF5C966"
VAULT_SUSDE = "0x87506fad05178F701e6E3bC9697c5AB264f5ffE6"
VAULT_EETH_KARAK = "0x2a35f99CC322626e48AC80aB3aF4C5DE2A910ef4"
VAULT_USDE_KARAK = "0x61F6A5687983D4a61283c65006c36DCdEC67853D"
#---------------------------

def generate(market, asset, name=None, symbol=None):
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

    if name is None:
        pt_name = pt.name()
        name = "Adapter " + " ".join(pt_name.split(" ")[:-1])
    if symbol is None:
        pt_symbol = pt.symbol()
        symbol = "a" + "-".join( pt_symbol.split("-")[:2])
    decimals = pt.decimals()
    print(name, symbol, decimals)
    _asset = boa.load_abi("contracts/vendor/DAI.json", name="ERC20").at(asset)
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
            PENDLE_ORACLE,
            gas = 150000
        ) #90807
    if factory.governance_impl() != GOVERNANCE:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 45816 * gas_price/10**18, " ETH")
        input("Going to deploy set governance settings into factory (ctrl+c to abort, enter to continue)")
        factory.update_governance(GOVERNANCE, gas=100000) #45816
    if factory.funds_allocator_impl() != FUNDS_ALLOCATOR:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 45816 * gas_price/10**18, " ETH")
        input("Going to deploy set fundsallocator settings into factory (ctrl+c to abort, enter to continue)")
        factory.update_funds_allocator(FUNDS_ALLOCATOR, gas=100000) #45816
    if factory.adapter_vault_blueprint() != ADAPTERVAULT_BLUEPRINT or factory.pendle_adapter_blueprint() != PENDLE_ADAPTER_BLUEPRINT:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 68330 * gas_price/10**18, " ETH")
        input("Going to deploy set blueprint into factory (ctrl+c to abort, enter to continue)")
        factory.update_blueprints(ADAPTERVAULT_BLUEPRINT, PENDLE_ADAPTER_BLUEPRINT, gas=200000) #68330


    if factory.owner() != MULTISIG:
        print("estimated gas price is: ", gas_price/10**9, " gwei")
        print("estimated gas cost: ", 28269 * gas_price/10**18, " ETH")
        input("Going to change owner of factory (ctrl+c to abort, enter to continue)")
        factory.replace_owner(MULTISIG, gas=50000) #28269
