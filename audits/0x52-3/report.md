# Adapter Fi Single Commit Audit Report

### Reviewed by: 0x52 ([@IAm0x52](https://twitter.com/IAm0x52))

### Review Date(s): 6/28/24

# 0x52 Background

As an independent smart contract auditor I have completed over 100 separate reviews. I primarily compete in public contests as well as conducting private reviews (like this one here). I have more than 30 1st place finishes (and counting) in public contests on [Code4rena](https://code4rena.com/@0x52) and [Sherlock](https://audits.sherlock.xyz/watson/0x52). I have also partnered with [SpearbitDAO](https://cantina.xyz/u/iam0x52) as a Lead Security researcher. My work has helped to secure over $1 billion in TVL across 100+ protocols.

# Scope

Only the very small subset of changes made in commit [148e0df](https://github.com/adapter-fi/AdapterVault/commit/148e0df4aabc104ac0ec913897dd2ccc3b67ba10) were reviewed and any other changes were not considered.

In-Scope Contracts

- contracts/adapters/PendleAdapter.vy

Deployment Chain(s)

- Ethereum Mainnet
- Arbitrum Mainnet

# Summary of Changes

The underlying pricing for Pendle PT's was changed. Previously each PT was valued against the underlying asset of the derivative (i.e. ETH for stETH PT) rather than derivative itself. This was leading to incorrect price quotes and reverting transactions. With this new methodology the PT (principle tokens) are quoted against the SY (standardized yield) token. SY tokens can be directly converted to the underlying derivative token via `previewWithdraw` or `previewDeposit` allowing proper pricing.

# Summary of Review

No vulnerabilities were found to have been introduced by these changes.
