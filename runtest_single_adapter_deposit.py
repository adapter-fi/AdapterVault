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
    dai.transfer(trader, 100000)

# We have to do this to deal with the false ownership issue
# in the mocklp adapter.
with boa.env.prank(adapt_junk.address):
    dai.approve(vault.address,1000000000)

with boa.env.prank(trader):
    dai.approve(vault.address,1000000000)    

### Setup done.

d4626_start_DAI = dai.balanceOf(vault)
LP_start_DAI = dai.balanceOf(adapt_junk)

trade_start_DAI = dai.at(adapt_junk.originalAsset()).balanceOf(trader)
trade_start_dyDAI = vault.balanceOf(trader)

assert vault.totalAssets() == 0
assert adapt_junk.totalAssets() == 0

assert vault.convertToShares(55) == 55
assert vault.convertToAssets(75) == 75

with boa.env.prank(trader):
    assert vault.totalAssetsCached() == 0
    assert 500 == vault.deposit(500, trader)

trade_end_DAI = dai.at(adapt_junk.originalAsset()).balanceOf(trader)
trade_end_dyDAI = vault.balanceOf(trader)

assert trade_start_DAI - trade_end_DAI == 500
assert trade_end_dyDAI - trade_start_dyDAI == 500
    
d4626_end_DAI = dai.balanceOf(vault)

# DAI should have just passed through the 4626 adapter.
assert d4626_end_DAI == d4626_start_DAI

LP_end_DAI = dai.balanceOf(adapt_junk)
assert LP_end_DAI - LP_start_DAI == 500

# Now do it again!
with boa.env.prank(trader):
    assert 400 == vault.deposit(400, trader)

assert vault.balanceOf(trader) == 900

trade_end_DAI = dai.at(adapt_junk.originalAsset()).balanceOf(trader)
trade_end_dyDAI = vault.balanceOf(trader)

assert trade_start_DAI - trade_end_DAI == 900
assert trade_end_dyDAI - trade_start_dyDAI == 900
    
d4626_end_DAI = dai.balanceOf(vault)

# DAI should have just passed through the 4626 adapter.
assert d4626_end_DAI == d4626_start_DAI

LP_end_DAI = dai.balanceOf(adapt_junk)
assert LP_end_DAI - LP_start_DAI == 900  

print("runtest_single_adapter_deposit.py complete.")
