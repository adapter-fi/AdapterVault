# How would reverts from upstream break our 4626




|  |`maxWithdraw()`|`maxDeposit()`|`totalAssets()`|`deposit()`|`withdraw()`|
|--|---------------|--------------|---------------|-----------|----------|
|AAVE|Works fine|Works fine|Works fine|reverts error="29"|reverts error="29"|
|compound|Works fine|Works fine|Works fine|can revert `MintComptrollerRejection`|can revert `RedeemComptrollerRejection`|
|euller|Works fine|Works fine|Works fine|Works fine|Works fine|
|fraxlend|Works fine|Works fine|Works fine|Works fine|Works fine|



## AAVE

I could find 3 ways in which AAVE can be paused. 
1. Pausing individual asset `PoolConfigurator.setReservePause(0xAsset, true)`
2. Pausing all of AAVE `PoolConfigurator.setPoolPause(true)` (which basically pauses each asset inside a forloop)
3. All AAVE contracts are upgradable, so there can be unknown way the contract is paused/exploited/rug-pulled.

PS: Adapter can probe this. Look at `is_active()` method of aaveAdapter.vy . Current code uses this to return 0 as `maxDeposit()` and `maxWithdraw()`. There might be very tiny amount of gas savings if we dont do this check and let it revert. The savings is not a lot as deposit/withdraw would eventually read the same storage slot.

The idea is that `maxDeposit()` and `maxWithdraw()` return some value, and as long as the strategy adheres to the returned values the subsiquent deposit() or withdraw() should not revert.

current logic

- `maxDeposit()` = max_supply minus assets deposited . TODO: current implementation is max_supply - totalSupply, but in reality amount accrued to treasury also needs to be taken into account. [Relavent upstream check](https://github.com/aave/aave-v3-core/blob/94e571f3a7465201881a59555314cd550ccfda57/contracts/protocol/libraries/logic/ValidationLogic.sol#L57)
- `maxWithdraw()` = min(adapter balance of the asset, the asset currently available in aave) . TODO: Validate if this is true . [Relavent upstream check](https://github.com/aave/aave-v3-core/blob/94e571f3a7465201881a59555314cd550ccfda57/contracts/protocol/libraries/logic/ValidationLogic.sol#L87)

## Compound

The code for fetching the exchange rate looks benign, not revert-ey.

current logic

- `maxWithdraw()` : min(adapter balance of the asset, the asset currently available in compound)
- `maxDeposit()` : maxuint256

PS: `maxWithdraw()` and `maxDeposit()` currently does not take reality into account, so theres a chance of revert during actual withdraw/deposit


So far it appears that only place compound will revert during deposit is in CToken.sol line 400

```solidity
        uint allowed = comptroller.mintAllowed(address(this), minter, mintAmount);
        if (allowed != 0) {
            revert MintComptrollerRejection(allowed);
        }
```

I think this is compounds blacklist impl and also a way to pause...

Withdraw also has a similar check at CToken.sol line 508

```solidity
        uint allowed = comptroller.redeemAllowed(address(this), redeemer, redeemTokens);
        if (allowed != 0) {
            revert RedeemComptrollerRejection(allowed);
        }

        //few lines later

        comptroller.redeemVerify(address(this), redeemer, redeemAmount, redeemTokens);
```

## Euller

It's a bit hard to trace thru eullers code path, particularly because the entire thing is a complex web of "modules".

It does not appear to revert on anything aside from obvious bad inputs (like wrong amounts, no approval, etc).

I can't see any pause mechanism, or any supply cap and such, maybe I'm missing some validation hook somewhere?

## Fraxlend

Same as Euller, there doesnt seem to be any permission check or such.

Just that withdraw as this check (FraxlendPairCore.sol line 288 - 298)

```solidity
    /// @notice The ```_totalAssetAvailable``` function returns the total balance of Asset Tokens in the contract
    /// @param _totalAsset VaultAccount struct which stores total amount and shares for assets
    /// @param _totalBorrow VaultAccount struct which stores total amount and shares for borrows
    /// @return The balance of Asset Tokens held by contract
    function _totalAssetAvailable(VaultAccount memory _totalAsset, VaultAccount memory _totalBorrow)
        internal
        pure
        returns (uint256)
    {
        return _totalAsset.amount - _totalBorrow.amount;
    }
```

The adapter calculates `maxWithdraw()` using the amount of asset available by the fraxlend contract, however fraxlend uses internal counters, essentially for the same purpose. There is a remote chance that these values can drift, and even lesser likely for us to hit it.
