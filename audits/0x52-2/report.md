# Adapter Fi Report

### Reviewed by: 0x52 ([@IAm0x52](https://twitter.com/IAm0x52))

### Review Date(s): 6/9/24 - 6/10/24

### Fix Review Date(s): 6/13/24

### Fix Review Hash: [a66037f](https://github.com/adapter-fi/AdapterVault/tree/a66037feaf156f0e7195d949f0ed3ce6a716e94c)

# 0x52 Background

As an independent smart contract auditor I have completed over 100 separate reviews. I primarily compete in public contests as well as conducting private reviews (like this one here). I have more than 30 1st place finishes (and counting) in public contests on [Code4rena](https://code4rena.com/@0x52) and [Sherlock](https://audits.sherlock.xyz/watson/0x52). I have also partnered with [SpearbitDAO](https://cantina.xyz/u/iam0x52) as a Lead Security researcher. My work has helped to secure over $1 billion in TVL across 100+ protocols.

# Scope

The [Adapter Fi](https://github.com/adapter-fi/) repo was reviewed at commit hash [c7c6de9](https://github.com/adapter-fi/AdapterVault/commit/c7c6de9d512e4c33056c752aa9b2bec77516463a)

In-Scope Contracts

- contracts/AdapterVault.vy
- contracts/FundsAllocator.vy
- contracts/Governance.vy
- contracts/PTMigrationRouter.vy
- contracts/PendleVaultFactory.vy

Deployment Chain(s)

- Ethereum Mainnet
- Arbitrum Mainnet

# Summary of Findings

| Identifier | Title                                                                                                                      | Severity | Mitigated |
| ---------- | -------------------------------------------------------------------------------------------------------------------------- | -------- | --------- |
| [L-01]     | [Adapter maximum withdrawal may be bypassed in some cases](#l-01-adapter-maximum-withdrawal-may-be-bypassed-in-some-cases) | LOW      | ✔️        |
| [L-02]     | [Strategy APY checks are impossible to enforce](#l-02-strategy-apy-checks-are-impossible-to-enforce)                       | LOW      | ✔️        |
| [QA-01]    | [Voting for new governance will emit incorrect event](#qa-01-voting-for-new-governance-will-emit-incorrect-event)          | QA       | ✔️        |
| [QA-02]    | [Voting event isn't descriptive and lacks key information](#qa-02-voting-event-isnt-descriptive-and-lacks-key-information) | QA       | ✔️        |
| [QA-03]    | [Redundant assert statement](#qa-03-redundant-assert-statement)                                                            | QA       | ✔️        |
| [QA-04]    | [Voting events are emitted with incorrect information](#qa-04-voting-events-are-emitted-with-incorrect-information)        | QA       | ✔️        |

# Detailed Findings

## [L-01] Adapter maximum withdrawal may be bypassed in some cases

### Details

[FundsAllocator.vy#L65-L73](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/FundsAllocator.vy#L65-L73)

    if adapter.ratio == 0 and adapter.current > 0:
        adapter.target = 0
        adapter.delta = max(convert(adapter.current, int256)*-1, adapter.max_withdraw) # Withdraw it all!
        target_withdraw_balance -= min(convert(adapter.delta * -1, uint256),target_withdraw_balance)


    elif adapter.current > 0:
        withdraw : uint256 = min(target_withdraw_balance, adapter.current)
        target_withdraw_balance = target_withdraw_balance - withdraw
        adapter.delta = convert(withdraw, int256) * -1

Adapters are configured with max withdrawal parameters to prevent vault freezing or excess slippage from large withdrawals. This has been applied when processing blocked or removed adapters but fails to apply to user initiated withdrawals. Since all withdrawals contain user supplied slippage parameters, the worst case impact of this is reverting transactions and no funds are at risk.

### Lines of Code

[FundsAllocator.vy#L37-L86](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/FundsAllocator.vy#L37-L86)

### Recommendation

For active adapters, `withdraw` should be capped at `adapter.max_withdraw`

### Remediation

Fixed as recommended in commit [3a170d4](https://github.com/adapter-fi/AdapterVault/commit/3a170d4615d0a18991ff4f3dd4a052aa9e99392c).

## [L-02] Strategy APY checks are impossible to enforce

### Details

[Governance.vy#L79-L92](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L79-L92)

struct Strategy:
Nonce: uint256
ProposerAddress: address
LPRatios: AdapterStrategy[MAX_ADAPTERS]
min_proposer_payout: uint256
APYNow: uint256
APYPredicted: uint256
TSubmitted: uint256
TActivated: uint256
Withdrawn: bool
no_guards: uint256
VotesEndorse: DynArray[address, MAX_GUARDS]
VotesReject: DynArray[address, MAX_GUARDS]
VaultAddress: address

When supplying a new strategy the above struct is supplied with APY estimates of both the current and proposed strategies.

[Governance.vy#L169-L170](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L169-L170)

    # Confirm strategy meets financial goal improvements.
    assert strategy.APYPredicted - strategy.APYNow > 0, "Cannot Submit Strategy without APY Increase"

During validation of the strategy these values are compared. The issue is that both values are user supplied making this check impossible to accurately enforce. This check is vestigial from when strategy proposals were permissionless.

### Lines of Code

[Governance.vy#L132-L194](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L132-L194)

### Recommendation

Only trusted parties are allowed to submit proposals so I would recommend a removal of the APY system completely to reduce code size and complexity.

### Remediation

Fixed by removing APY system completely in commit [d75679a](https://github.com/adapter-fi/AdapterVault/commit/d75679a7bf6547e8454bd89a56229b79fca53dce).

## [QA-01] Voting for new governance will emit incorrect event

### Details

[Governance.vy#L510-L518](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L510-L518)

    if len(self.LGov) == VoteCount:
        AdapterVault(vault).replaceGovernanceContract(NewGovernance)

        # Clear out the old votes.
        for guard_addr in self.LGov:
            self.VotesGCByVault[vault][guard_addr] = empty(address)


    log GovernanceContractChanged(Voter, NewGovernance, VoteCount, TotalGuards)

The `GovernanceContractChanged` event is always emitted when calling `replaceGovernance` even when there are not enough votes to replace the contract. This can lead to manipulated events that do not reflect the true onchain status.

### Lines of Code

[Governance.vy#L471-L518](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L471-L518)

### Recommendation

Indent the event log so that it will only emit if there are enough votes to replace the old governance

### Remediation

Fixed as recommended in commit [f0adb76](https://github.com/adapter-fi/AdapterVault/commit/f0adb76619094c0afb05a8ce054e4a962f64de5e).

## [QA-02] Voting event isn't descriptive and lacks key information

### Details

[Governance.vy#L500](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L500)

    if self.VotesGCByVault[vault][msg.sender] != NewGovernance:
        log VoteForNewGovernance(NewGovernance)

Here the `VoteForNewGovernance` event is emitted. This lacks many key pieces of information like who is voting and which vault it is for.

### Lines of Code

[Governance.vy#L471-L518](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L471-L518)

### Recommendation

Utilize the `StrategyVote` event instead to ensure more descriptive events are recorded

### Remediation

Fixed in commit [2b8c2bf](https://github.com/adapter-fi/AdapterVault/commit/2b8c2bf7b16503acf2ee82244600347e2f35fbbe) by adding a voter field to the `VoteForNewGovernance` event.

## [QA-03] Redundant assert statement

### Details

[Governance.vy#L133-L139](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L133-L139)

    assert msg.sender in self.LGov, "Only Guards may submit strategies."

    if self.NextNonceByVault[vault] == 0:
        self.NextNonceByVault[vault] += 1

    # No Strategy proposals if no governance guards
    assert len(self.LGov) > 0, "Cannot Submit Strategy without Guards"

Above there are two checks, first that msg.sender is contained in LGov and second that LGov is not empty. The length check is redundant and can never be triggered because in the event that there are no guards, msg.sender can never be contained in LGov.

### Lines of Code

[Governance.vy#L132-L194](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L132-L194)

### Recommendation

The length check should either be moved to before the authority check to ensure an accurate error message or it should be removed entirely to reduce code length and complexity.

### Remediation

Fixed in commit [1cf7d74](https://github.com/adapter-fi/AdapterVault/commit/1cf7d7486b04958b7fa858e8fe69f02587eafd3e) by removing LGov length check

## [QA-04] Voting events are emitted with incorrect information

### Details

[Governance.vy#L269](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L269)

    log StrategyVote(Nonce, vault, msg.sender, False)

When endorsing a strategy the `endorsed` bool is emitted as `False` when it should instead be `True`. This is also true of `rejectStrategy` which emits `True` instead of `False`

### Lines of Code

[Governance.vy#L269](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L269)

[Governance.vy#L313](https://github.com/adapter-fi/AdapterVault/blob/e8caa31abadb3004a132af369c4dfdbf420d922c/contracts/Governance.vy#L313)

### Recommendation

Correct event to emit correct bool in each case

### Remediation

Fixed as recommended in commit [8a31553](https://github.com/adapter-fi/AdapterVault/commit/8a315533a1bf1f5e758ded1c47350f88a3292baa)
