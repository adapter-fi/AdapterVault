import boa
from decimal import Decimal

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

	vault = boa.load("contracts/AdapterVault.vy","BigVault","vlt",2, dai, [adapt_junk,], gov, alloc, Decimal(2.0))

strategy = [(ZERO_ADDRESS,0)] * MAX_ADAPTERS 
strategy[0] = (adapt_junk.address, 1)

with boa.env.prank(gov.address):
        vault.set_strategy(owner, strategy, 0)

with boa.env.prank(owner):
	dai.mint(owner, 1000000)
	dai.transfer(vault,20000)

	dai.transfer(trader, 100000)

assert dai.balanceOf(vault) == 20000

with boa.env.prank(owner):
	vault.balanceAdapters(10)	
	vault.balanceAdapters(42)
	vault.balanceAdapters(10)	


assert dai.balanceOf(vault) == 10
assert dai.balanceOf(adapt_junk) == 19990

#with boa.env.prank(trader):
#	vault.deposit(1000, trader)

