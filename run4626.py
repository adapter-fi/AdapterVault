import boa
import math
from decimal import Decimal
#from titanoboa.debug import breakpoint

#alchemy_key = 'rmrr6rVlDSKKSZB5Npk2As2VZDwcU60s'
#block_id=19850000
#fork_uri="https://eth-mainnet.g.alchemy.com/v2/" + alchemy_key
#boa.env.fork(fork_uri, block_identifier=block_id)


ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MAX_ADAPTERS = 5 # Must match the value from AdapterVault.vy


owner = boa.env.generate_address('owner')
boa.env.set_balance(owner, 10*8**10)

trader = boa.env.generate_address('trader')
boa.env.set_balance(trader, 10*8**10)


with boa.env.prank(owner):
    dai = boa.load("contracts/test_helpers/ERC20.vy","Dai","Dai",2,10*10**18,owner)
    junk = boa.load("contracts/test_helpers/ERC20.vy","Junk","Junk",2,10*10**18,owner)

    adapt_junk = boa.load("contracts/adapters/MockLPAdapter.vy", dai, junk)
 
    gov = boa.load("contracts/Governance.vy",owner,21600)

    alloc = boa.load("contracts/FundsAllocator.vy")
    
    vault = boa.load("contracts/AdapterVault.vy","BigVault","vlt",2, dai, gov, alloc, Decimal(2.0))
    vault.add_adapter(adapt_junk)

strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
strategy[0] = (adapt_junk.address, 1)

with boa.env.prank(gov.address):
    vault.set_strategy(owner, strategy, 0)

with boa.env.prank(owner):
    dai.mint(owner, 1000000)
    dai.transfer(vault,20000)

    dai.transfer(trader, 100000)

assert dai.balanceOf(vault) == 20000

# We have to do this to deal with the false ownership issue
# in the mocklp adapter.
with boa.env.prank(adapt_junk.address):
    dai.approve(vault.address,1000000000)

with boa.env.prank(owner):
    vault.balanceAdapters(10)
    vault.balanceAdapters(42)
    vault.balanceAdapters(10)


assert dai.balanceOf(vault) == 10
assert dai.balanceOf(adapt_junk) == 19990

assert vault.totalAssets() == 20000

with boa.env.prank(owner):
    print("vault before balance = ", vault.totalAssets())
    print("removing owner balance: ", vault.balanceOf(owner))
    vault.withdraw(vault.balanceOf(owner), owner, owner)
    print("vault after balance = ", vault.totalAssets())

with boa.env.prank(trader):
    print("vault before balance = ", vault.totalAssets())
    print("removing trader balance: ", vault.balanceOf(trader))
    vault.withdraw(vault.balanceOf(trader), trader, trader)
    print("vault balance = ", vault.totalAssets())
    dai.approve(vault.address,1000)
    vault.deposit(1000, trader) #, 1000)

    d4626_assets, adapter_states, total_assets, total_ratios = vault.getCurrentBalances()

    assert d4626_assets == 0
    assert adapter_states[0][0] == adapt_junk.address
    assert adapter_states[0][1] == 21000
    assert adapter_states[0][2] == 21000
    assert adapter_states[0][5] == 1 
    #assert adapter_states[0].target == 0
    #assert adapter_states[0].delta== 0
    assert total_assets == 21000
    assert total_ratios == 1   

# vault.withdraw(500, trader, trader)

# current_assets = vault.totalAssets()
# steal = int(math.ceil(current_assets * .27))# Steal 27% of the assets.
# print("vault balance = ", vault.totalAssets(), "but stealing ", steal)

# with boa.env.prank(adapt_junk.address):
# dai.transfer(owner,steal)
# print("vault balance = ", vault.totalAssets())

# with boa.env.prank(trader):
# #vault.withdraw(300, trader, trader)
# dai.approve(vault.address,100)
# vault.deposit(100, trader)
# dai.approve(vault.address,100)
# vault.deposit(100, trader)
# print("vault balance = ", vault.totalAssets())
# vault.withdraw(200, trader, trader)

print("run4626.py complete.")
