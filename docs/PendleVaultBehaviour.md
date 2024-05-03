# Pendle vault

Currently, the pendle vault only supports a single *active* adapter/market at a time. The idea is to add future improvements to FundsAllocator to support multi-market arbitrage.

Well the vault can support multiple active adapters but deposit/withdrawals get very costly in terms of gas with current FundsAllocator.

## Exchange rate

Each adapter determines its PT <--> asset exchange rate using `PendlePtLpOracle.getPtToAssetRate(pendleMarket, TWAP_DURATION)` , TWAP_DURATION is a constant configured to be 900(seconds). The adapter uses this to figure out its assets under management.

The vault determines its exchange rate using sum of each adapters balance and total supply of its own shares.


Assume

|Vault share total supply|Vault Cash|Adapter PT balance|Adapter Asset Balance|total AUM|
|------------------------|----------|---|---------------------|---------|
|         100 SHARE      | 5 stETH|200 PT|100 stETH|105 stETH|

(assuming oracle says 1 PT = 0.5 stETH)

In this case 1 SHARE = 105/100 = 1.05 stETH


## Deposit

During deposit, the users funds(and any lingering cash balance) are deposited into the active market. Post deposit, the adapters asset balance is rechecked and *slippage* is calculated. 

slippage = (amount of assets being deposited ) - (asset value increase of adapter per TWAP oracle)

The vault checks for default minimum slippage (currently set to 2%) or uses optional _min_shares argument as the minimum allowed slippage.

Any positive slippage remains in the adapter (this is bonus yield).

NOTE: Currently only AMM swap is supported for deposit. A future version of adapter will dynamically choose between AMM swap vs "zapping", whichever gets a higher amount of PT.


|Vault share total supply|Vault Cash|Adapter PT balance|Adapter Asset Balance|total AUM|
|------------------------|----------|---|---------------------|---------|
|         100 SHARE      | 5 stETH|200 PT|100 stETH|105 stETH|

(assuming oracle says 1 PT = 0.5 stETH)

In this case 1 SHARE = 105/100 = 1.05 stETH

A user deposits 100 stETH, based on above math he should get 95.238 SHARES, however...

As part of users deposit, the vault tried depositing 105 stETH(5 stETH from before lingering as cash balance) to pendle, instead of getting back 52.5 PT, only 51 PT was returned due to slippage. The vault's AUM only increased by 102 stETH.

In this case, the user would get back only 95.238 * 102 / 105 = 92.5169 SHARES, a slippage of 2.857% (this would need to pass either user provided threshold if minimum shares out, or the default configured slippage).

## Withdrawal

During withdrawal, the adapter fist calculates the amount of PT to exchange using TWAP oracle, then swaps the calculates PT amount to assets.

The Vault checks the increase in asset amount, if it was lower than expected, does slippage checks similar to how its described in deposit section, if its higher then the excess is left in the vault as cash balance (it would get deposited back as part of a subsequent deposit)

Upon maturity 1 PT = 1 Asset. The TWAP reflects the peg, and the withdrawal is done using redemption and not AMM swap and the rate is pegged so no slippage.


|Vault share total supply|Vault Cash|Adapter PT balance|Adapter Asset Balance|total AUM|
|------------------------|----------|---|---------------------|---------|
|         100 SHARE      | 5 stETH|200 PT|100 stETH|105 stETH|

(assuming oracle says 1 PT = 0.5 stETH)

In this case 1 SHARE = 105/100 = 1.05 stETH

A user wants to withdraw 52.5 stETH (half if the vault), this would cost him 50 SHARES.

The vault asks the adapter to withdraw 47.5 stETH (because it already has 5 stETH cash).

The adapter swaps 23.75 and gets back only 47 stETH, loss of 0.5 stETH due to slippage.

The vault is ready to give the user 52 stETH (does a slippage assertion first similar to in deposit). There wouldn't be any slippage in case the adapter being withdrawn from was at maturity.

## "auto" compounding

Nearing maturity, the vault owner deploys a new adapter pointing to new market. The strategy is updated to allocate 0% to the old(almost matured) adapter and 100% to the new adapter. The effect of this is withdrawals happen from the old and new deposits go into the new. This way, depending on end-user activity, some of the slippage for liquidity re-allocation would be paid by users and not the vault.

Some time post-maturity, vault owner removes the old adapter, triggering a rebalance, this causes a no-slippage withdrawal from the mature adapter and deposits into the new adapter (currently only supports AMM swap). This deposit would have slippage, **this slippage is socialized by the vault**. We work under the assumption that the owner is trustworthy, will not frontrun the interaction, and will take every precaution to not be visible in the mempool.

## Misc stuff

### swap_pools

Gives owner ability to change adapter address without rebalancing. The goal is to be able to "upgrade" adapter code without paying the round-trip slippage for moving funds around.

### How would frontend compute APY

TODO
