
import os
import pytest
import boa
import json
from boa.environment import Env
from web3 import Web3
import eth_abi
from decimal import Decimal

from tests_boa.conftest import forked_env_mainnet

PENDLE_ROUTER="0x00000000005BBB0EF59571E58418F9a4357b68A0"
NOTHING="0x0000000000000000000000000000000000000000"
PENDLE_ROUTER_STATIC="0x263833d47eA3fA4a30f269323aba6a107f9eB14C"

PENDLE_ORACLE="0x66a1096C6366b2529274dF4f5D8247827fe4CEA8"
UNISWAP_ROUTER="0xE592427A0AEce92De3Edee1F18E0157C05861564"
MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935
VAULT_RSWETH = "0xe6cD0b7800cA3e297b8fBd7697Df9E9F6A27f0F5"
RSWETH="0xFAe103DC9cf190eD75350761e95403b7b8aFa6c0"



@pytest.fixture
def setup_chain():
    with boa.swap_env(Env()):
        #tests in this file require mainnet block 20332460: Jul-18-2024 09:17:47 AM +UTC
        forked_env_mainnet(20332460)
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
def pendle_migrator(setup_chain, deployer):
    with boa.env.prank(deployer):
        pa = boa.load("contracts/PTMigrationRouter.vy", PENDLE_ROUTER, UNISWAP_ROUTER)
    return pa


@pytest.fixture
def pendleRouter(setup_chain):
    with open("contracts/vendor/IPAllActionV3.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="IPAllActionV3")
    return factory.at(PENDLE_ROUTER)

def _generic_erc20(trader, addr, slot):
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
    st = factory.at(addr)
    #Trader needs to acquire some ETH, dunno how
    abi_encoded = eth_abi.encode(['address', 'uint256'], [trader, slot])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()])

    boa.env.set_storage(
        boa.util.abi.Address(addr).canonical_address,
        Web3.to_int(storage_slot),
        5000 * 10**18
    )
    print(st.balanceOf(trader))
    print(boa.env.get_balance(trader))
    assert st.balanceOf(trader) >= 5000 * 10**18, "Trader did not get 'airdrop'"
    return st

def test_pt_migration_eeth_zap_uni(setup_chain, trader, pendleRouter, pendle_migrator):
    #testing PT-eeth to adapter-rsweth zap using migration contract
    #init live rswETH vault
    vault = boa.load_partial("contracts/AdapterVault.vy").at(VAULT_RSWETH)
    #"airdrop" WEETH to trader..
    WEETH = "0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee"
    weeth = _generic_erc20(trader, WEETH, 101)
    #trader buys some PT
    MARKET="0xe1F19CBDa26b6418B0C8E1EE978a533184496066"
    PT = "0xe146E7018B3fb588c4EFbC2F211e8BB8d8C31c81"
    with open("contracts/vendor/IERC20.json") as f:
        j = json.load(f)
    factory = boa.loads_abi(json.dumps(j["abi"]), name="ERC20")
    pt = factory.at(PT)

    with boa.env.prank(trader):
        weeth.approve(pendleRouter, 10*10**18)
        ap = (
            0, #guessMin
            MAX_UINT256, #guessMax
            0, #guessOffchain
            256, #maxIteration
            10**14 #eps
        )
        ti = (
            WEETH, #tokenIn
            10*10**18, #netTokenIn
            WEETH, #tokenMintSy
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

        pendleRouter.swapExactTokenForPt(trader, MARKET, 0, ap, ti, limit)
        pt_bal = pt.balanceOf(trader)
        pt_bal_vault = pt.balanceOf(vault)
        print("pt_bal", pt_bal)

    #zap function
    with boa.env.prank(trader):
        #first aprove the migration router...
        pt.approve(pendle_migrator, 10**18)

        #path is WEETH ->  [0.01%] WETH --> [0.05%]  RSWETH 
        WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        #meh cant find abi.encodePacked in python lib, doing ugly string manipulations
        path = b''
        path += eth_abi.encode(["address"], [WEETH])[-20:]
        path += eth_abi.encode(["uint24"], [100])[-3:]
        path += eth_abi.encode(["address"], [WETH])[-20:]
        path += eth_abi.encode(["uint24"], [500])[-3:]
        path += eth_abi.encode(["address"], [RSWETH])[-20:]
        print(path.hex())
        pendle_migrator.zap_in_univ3(
            MARKET,
            10**18,
            WEETH,
            0,
            limit,
            path,
            RSWETH,
            0,
            VAULT_RSWETH,
            0,
        )
    
