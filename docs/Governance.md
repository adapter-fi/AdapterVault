# Adapter.Fi <-> Governance Contract

## Summary

The Adapter.Fi protocol crowd sources optimal wealth allocations across various liquidity/lending platforms. Such an
allocation, proposed or active, is called a Strategy. The expectation that just about anyone is allowed to propose a Strategy introduces a likely significantly higher rate of submissions across the Ethereum ecosystem. The typical voting method of deciding which decision to make is both unweildy and would require far too much active participation by others who have investments in the Adapter.Fi protocol. On the other hand, if the protocol has no restrictions on who and when Strategies can be proposed nor a process in which to edjudicate their acceptance, bad actors could use this openess as a vector to attempt denial of service attacks that would break down then entire value of the protocol. 

Adapter.Fi has adopted a Governance policy that is optimistic in assuming most submitted Strategies are valid so, unless someone involved in Governance makes the effort to reject a Strategy, it will ultimately be accepted and activated in a reasonable period of time. To protect against bad actors, however, there is a "decision period" that starts when a new Strategy is proposed in which a select group of Governance Guards may choose to block an invalid Strategy. Optionally, the Guards may even short circuit the waiting time by having an absolute majority vote to endorse the Strategy so it may be activated right away. 

This DAO-like governance model assumes Strategies proposed are valid and should be accepted by default. Guards need only intervene if a proposed Strategy appears to be something other than it claims to be or if there is an exceptional situation where either market forces or ecosystem issues introduce an urgency for the existing active Strategy to be replaced as quickly as possible. 

### Proposing a Strategy

To propose a new Strategy, four conditions must be met:
1) The Proposer must meet the qualifications to make a proposal. (P<sub>E</sub> - see below.)
2) The Proposer must not be subject to some explicit prohibition from submitting strategies. (P<sub>X</sub> - see below.)
3) There must not be a proposed Strategy that is still pending during the "decision period" or "activation period".
4) The proposed Strategy must meet certain criteria in terms of minimum margin of improvement requirements.

A proposed Strategy contains both the wealth allocation recommendations as well as the claims for what the current Strategy's yield, APY<sub>CURRENT</sub>, is and what the proposed Strategy's yield, APY<sub>PROPOSED</sub>, would be. The Governance DAO contract will confirm the first three conditions authoritatively. So long as APY<sub>PROPOSED</sub> - APY<sub>CURRENT</sub> > the minimum improvement, APY<sub>DELTA</sub>, then condition #4 is assumed to be met by the Governance DAO contract but it assumes that external Guards will check that the claims are within spec and take action to prevent its activation if not.

The "decision period" now starts and no other Strategy can be proposed until this one is properly adjudicated.


#### submitStrategy

*Given:*

P<sub>E</sub> = Predicate - Proposer must meet certain qualification for eligibility. (Must resolve to True)

- Ex: hold a certain quantity of vault tokens. TBD

P<sub>X</sub> = Predicate - Proposer must not be subject to some form of exclusion. (Must resolve to False)

- Ex: having been rejected in last 24 hrs or on a black list. TBD

T<sub>DELAY</sub> = Variable - How long after a strategy is submitted until it can be activated so long as it is not rejected/overwhelmingly endorsed.

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.

Strategy = (Proposed) Struct = { Nonce, Proposer Addr, Weights[], T<sub>SUBMITTED</sub>, T<sub>ACTIVATED</sub>, Withdrawn, len(L<sub>GOV</sub>), Votes<sub>ENDORSE</sub>, Votes<sub>REJECT</sub> }


```mermaid
sequenceDiagram

    participant P as Proposer
    participant C1 as Governance Contract
    participant N as Ethereum Network

    autonumber

    Note over P: Pre-Conditions:<br>Addr=User.wallet<br>Weights=[list of lending platform weights]<br>APYNow=(user calculation)<br>APYPredicted=(user calculation)<br>Strategy = {Nonce=0, Addr, Weights, APYNow, APYPredicted}
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current Active Strategy)<br> self.PendingStrategy = (Current Pending Strategy) <br> self.PendingStrategy= (self.CurrentStrategy || some other)<br>self.NextNonce=(next StrategyID > 0)<br>self.TDelay=(wait time for proposed Strategy)<br>self.MinimumAPYIncrease=(min improvement to consider Strategy)<br>self.LGOV = list of Governance Voter addresses

    P->>C1:submitStrategy(Strategy)
    Note over C1: No Strategy proposals if no governance guards <br> len(self.LGOV) > 0
    Note over C1: Confirm No Currently Pending Strategy<br>(likely incomplete TBD)<br>self.CurrentStrategy==self.PendingStrategy ||<br>self.PendingStrategy.Withdrawn==True ||<br>count(self.PendingVotesReject)>len(self.LGOV)/2 ||<br>(self.PendingStrategy.TSubmitted+(self.TDelay * 1.25) < now() and<br>count(self.PendingStrategy.VotesReject)>count(self.PendingStrategy.VotesEndorsed)
    C1 ->> C1: _noPendingStrategy() == True

    Note over C1: Confirm msg.sender Eligibility<br>(TBD)
    C1->>C1:PE() == True

    Note over C1: Confirm msg.sender is not blacklisted<br>(TBD)
    C1->>C1:PX() == FALSE

    Note over C1: Confirm Strategy.APYPredicted - Strategy.APYNow >= self.MinimumAPYIncrease

    Note over C1: Construct the New Strategy<br>TSubmitted=now()<br>TActive=0<br>Nonce=self.NextNonce<br>self.NextNonce+=1<br>VoterCount=len(self.LGOV)<br>Strategy={*Strategy,TSubmitted,TActive,Nonce,Withdrawn=False,VoterCount,VotesEndorse=[],VotesReject=[]}

    Note Over C1: self.PendingStrategy = Strategy

    C1-->>N: Emit Event StrategyProposal(Strategy)

    C1->>P: return self.PendingStrategy.Nonce
```

### Withdrawing a Strategy

If there is a Pending Strategy, the **original proposer** may elect to withdraw it at any time so that a new Strategy proposal can replace it. 

#### withdrawStrategy

```mermaid
sequenceDiagram

    participant P as Proposer
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber
    Note over P:<br> Pre-Conditions:<br> Nonce = (Nonce of previously submitted strategy)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active Strategy)<br> self.PendingStrategy = (Current Pending Strategy)
    P->>C1: withdrawStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy<br>(likely incomplete TBD)<br>self.CurrentStrategy != self.PendingStrategy 
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is the Strategy we want to withdraw <br> self.PendingStrategy.Nonce == Nonce
    Note over C1: Confirm Sender is the Strategy Proposer 
    Note over C1: Confirm msg.sender == self.PendingStrategy.ProposerAddress
    Note over C1:Set self.PendingStrategy.Withdrawn = True
    C1-->>N: Emit Event StrategyWithdrawal(Nonce)
    C1-->>P: return True
```

### Evaluating and Interceding on a Proposed Strategy

Adapter.Fi will operate bots that watch for StrategyProposal events and then also perform the calculations for determining the APY<sub>PROPOSED</sub> - APY<sub>CURRENT</sub> values for current and proposed Strategies. If the values resulting from the proposed Strategy's inputs coincide with the claimed values in the proposed Strategy as submitted then the bots can do nothing. If the values are significantly out of bounds then the bots will alert that the proposed Strategy is likely invalid so that Guards can decide to re-evaluate the proposed Strategy and reject the proposal if desired. 

A single rejection is enough to block a Proposed Strategy from being active if no other votes are made regarding the Proposed Strategy. If there is any rejection vote, the only way a Proposed Strategy can be enabled is for there to be a majority of Endorsement votes. Tied votes still result in a rejection. 

An absolute majority vote can enable the Proposed Strategy to short circuit the "decision period" time. At the time a Proposed Strategy is submitted, the number of Guards eligible to vote is tracked by the Proposed Strategy so that the potential vote count is known. Guards may be added or removed from the Governance Contract but the vote count that matters is based on the potential votes at the time the Proposed Strategy is submitted. If more than half the total potential votes are cast for rejection then a new Proposed Strategy may be submitted without waiting for the "decision period" to expire. If more than half the total potential votes are cast for endorsement then the current Proposed Strategy may be activated right away.

Guards may only vote once on a Proposed Strategy during the "activation period" and may not change their votes.

TODO?: In order to provide an absolute protection against on-going DOS race condition attacks by bad actors constantly proposing new Strategies, we could add an optional Strategy parameter to the `rejectStrategy` method which, if this reject vote results in an absolute rejection count, would immediately short circuit the waiting period and submit the new Strategy as a new Proposed Strategy. This may not be necessary if the predicates P<sub>E</sub> and P<sub>X</sub> are strong enough controls. It may also be the case, in the future, that Adapter.Fi may want a more strict separation of concerns and disallow Governance Guards to submit Strategies or vote on Strategies they've submitted - but this may not be practical in a true decentralized environment.


#### rejectStartegy

*Given:*

T<sub>DELAY</sub> = Variable - How long after a strategy is submitted until it can be activated so long as it is not rejected/overwhelmingly endorsed.

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.

Strategy = (Proposed) Struct = { Nonce, Proposer Addr, Weights[], T<sub>SUBMITTED</sub>, T<sub>ACTIVATED</sub>, Withdrawn, len(L<sub>GOV</sub>), Votes<sub>ENDORSE</sub>, Votes<sub>REJECT</sub> }


```mermaid
sequenceDiagram

    participant G as Guard
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber

    Note over G:<br> Pre-Conditions:<br>Nonce = (Nonce of previously submitted <br> StrategyProposalEvent that the guard wishes to reject)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active strategy)<br> self.LGOV = list of Guards <br> self.PendingStrategy = (Current Pending Strategy)
    G->>C1: rejectStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy <br> self.CurrentStrategy != self.PendingStrategy
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is the Strategy we want to Reject<br> self.PendingStrategy.Nonce == Nonce
    


    Note over C1: Confirm the Sender is a Guard Address in List of Guards
    Note over C1: msg.sender is in self.LGOV
    Note over C1: Confirm Sender has not yet voted 
    Note over C1: msg.sender is not in self.PendingStrategy.VoteReject and <br> msg.sender is not in self.PendingStrategy.VoteEndorse

    Note over C1:self.PendingStrategy.VoteReject.Append(msg.sender)



    C1-->>N: Emit Event StrategyVote(Nonce, GuardAddress, Endorse=False)

    C1-->>G: return True
```

#### endorseStartegy

*Given:*

T<sub>DELAY</sub> = Variable - How long after a strategy is submitted until it can be activated so long as it is not rejected/overwhelmingly endorsed.

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.

Strategy = (Proposed) Struct = { Nonce, Proposer Addr, Weights[], T<sub>SUBMITTED</sub>, T<sub>ACTIVATED</sub>, Withdrawn, len(L<sub>GOV</sub>), Votes<sub>ENDORSE</sub>, Votes<sub>REJECT</sub> }


```mermaid
sequenceDiagram

    participant G as Guard
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber

    Note over G:<br> Pre-Conditions:<br>Nonce = (Nonce of previously submitted <br> StrategyProposalEvent that the guard wishes to endorse)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active strategy)<br> self.LGOV = list of Guards <br> self.PendingStrategy = (Current Pending Strategy)
    G->>C1: endorseStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy  <br> self.CurrentStrategy != self.PendingStrategy 
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is the Strategy we want to Endorse <br> self.PendingStrategy.Nonce == Nonce


    Note over C1: Confirm the Sender is a Guard Address in List of Guards
    Note over C1: msg.sender is in self.LGOV
    Note over C1: Confirm Sender has not yet voted 
    Note over C1: msg.sender is not in self.PendingStrategy.VoteReject and <br> msg.sender is not in self.PendingStrategy.VoteEndorse

    Note over C1:self.PendingStrategy.VoteEndorse.Append(msg.sender)



    C1-->>N: Emit Event StrategyVote(Nonce, GuardAddress, Endorse=True)

    C1-->>G: return True
```


### Activating a Proposed Strategy

Assuming either no reject votes have occurred or a majority of votes for endorsement have been registered and either the "decision period" has passed or been short circuited, a new "activation period" starts which gives time for someone to make an activateStrategy call against the Governance Contract to make the Proposed Strategy the new Active Strategy. That time period is set to 25% of the "decision period" time. During this time no other Proposed Strategy can be submitted so long as the pending Proposed Strategy remains inactive. Note that ANYONE can call the `activateStrategy` function which credits the original proposer in terms of rewards but the actor making the function call pays the gas price for the function call and necessary rebalancing of the funds which could be expensive. 

Note that there is no expiration time for calling `activateStrategy` so long as the Proposed Strategy is still eligible. It does not matter if the "activation period" has passed. Until such time that a new Proposed Strategy is in place, the present one may be activated at will.

#### activateStrategy

*Given:*

T<sub>DELAY</sub> = Variable - How long after a strategy is submitted until it can be activated so long as it is not rejected/overwhelmingly endorsed.

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.

Strategy = (Proposed) Struct = { Nonce, Proposer Addr, Weights[], T<sub>SUBMITTED</sub>, T<sub>ACTIVATED</sub>, Withdrawn, len(L<sub>GOV</sub>), Votes<sub>ENDORSE</sub>, Votes<sub>REJECT</sub> }


```mermaid
sequenceDiagram

    participant A as Any Role
    participant C1 as Governance Contract
    participant D as AdapterVault
    participant N as Ethereum Network

    autonumber

    Note over A:<br> Pre-Conditions:<br>Nonce = (Nonce of previously submitted <br> StrategyProposalEvent that the guard wishes to endorse)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active Strategy)<br> self.TDelay=(wait time for proposed Strategy <br> self.PendingStrategy = (Current Pending Strategy)
    A->>C1: activateStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy <br>self.CurrentStrategy != self.PendingStrategy ||<br>self.PendingStrategy.Withdrawn==False 
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is Approved by Guards <br>count(self.PendingVotesEndorse)>len(self.LGOV)/2 ||<br>(self.PendingStrategy.TSubmitted+self.TDelay < now() and<br>count(self.PendingStrategy.VotesReject)<count(self.PendingStrategy.VotesEndorsed)
    Note over C1: Confirm Pending Strategy is the Strategy we want to Activate<br> self.PendingStrategy.Nonce == Nonce
    


    Note over C1:self.PendingStrategy = self.CurrentStrategy
    C1->>D: PoolRebalancer(self.CurrentStrategy)



    C1-->>N: Emit Event StrategyActivation(self.CurrentStrategy)

    C1-->>A: return True
```

### Governance of Governance

The Governance Contract Owner may add or remove Guards at will up to the limit of MAX_GUARDS.
The Governance Contract may be replaced with another one if 100% of all Guards vote to change to the same new Governance Contract. 

#### addGuard

*Given:*

Owner = Variable - Address of Governance Contract Owner

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.


```mermaid
sequenceDiagram

    participant OG as Owner
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber


    Note over C1: Pre-Conditions: <br> self.LGOV is the List of Current Guards <br> self.Owner is Governance Contract Owner Address <br> MAX_GUARDS is maximum count of guards

    OG->>C1: addGuard(GuardAddress)
    Note over C1: Confirm Sender is the Governance Contract Owner
    Note over C1: msg.sender == self.Owner
    Note over C1: Confirm the Guard being added is not in List of Guards
    Note over C1: GuardAddress is not in self.LGOV
    Note over C1: Confirm there is not the maximum amount of guards in the guard list
    Note over C1: len(self.LGOV) is less than MAX_GUARDS
    Note over C1: Confirm the Guard is a real address
    Note over C1: GuardAddress != ZERO_ADDRESS
    Note over C1: self.LGOV.Append(GuardAddress)


    C1-->>N: Emit Event NewGuard(GuardAddress)

    C1-->>OG: return True
```

#### removeGuard

*Given:*

Owner = Variable - Address of Governance Contract Owner

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.


Votes = map of Guard addr -> Contract Addr for votes on Governance Contract for Vault

```mermaid
sequenceDiagram

    participant OG as Owner
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber


    Note over C1: Pre-Conditions: <br> self.LGOV is the List of Current Guards <br> self.Owner is Governance Contract Owner Address <br>self.Votes = (map of Guards -> Addr)
    OG->>C1: removeGuard(GuardAddress)

    Note over C1: Confirm Sender is the Governance Contract Owner
    Note over C1: msg.sender == self.Owner
    Note over C1: Confirm the Guard being removed is in List of Guards
    Note over C1: GuardAddress is in self.LGOV

    Note over C1: Erase old Guard's vote<br>self.Votes[GuardAddress] = ZERO_ADDRESS    

    Note over C1: Replace Deleted Guard with Last Guard in List: <br> Index = position of GuardAddress in self.LGOV <br> Last_Pos = len(self.LGOV)<br> self.LGOV[Index] = self.LGOV[Last_Pos] <br> self.LGOV[Last_Pos] = ZERO_ADDRESS
    

    C1-->>N: Emit Event GuardRemoved(GuardAddress)

    C1-->>OG: return True
```

#### swapGuard

*Given:*

Owner = Variable - Address of Governance Contract Owner

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.

Votes = map of Guard addr -> Contract Addr for votes on Governance Contract for Vault


```mermaid
sequenceDiagram

    participant OG as Owner
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber

   
    Note over C1: Pre-Conditions: <br> self.LGOV is the List of Current Guards <br> self.Owner is Governance Contract Owner Address <br>self.Votes = (map of Guards -> Addr)
    OG->>C1: swapGuard(OldGuardAddress, NewGuardAddress)


    Note over C1: Confirm Sender is the Governance Contract Owner
    Note over C1: msg.sender == self.Owner 

    Note over C1: Confirm the New Guard being added is not in List of Guards<br>Note over C1: NewGuardAddress not in self.LGOV
    Note over C1: Confirm the Old Guard being removed is in List of Guards<br>OldGuardAddress in self.LGOV

    Note over C1: Confirm the New Guard is a real address<br>NewGuardAddress != ZERO_ADDRESS
    
    Note over C1: Erase old Guard's vote<br>self.Votes[OldGuardAddress] = ZERO_ADDRESS

    Note over C1: Replace Old Guard with New Guard: <br> Index = position of OldGuardAddress in self.LGOV <br>  self.LGOV[Index] = NewGuardAddress


    C1-->>N: Emit Event GuardSwap(OldGuardAddress, NewGuardAddress)

    C1-->>OG: return True
```

#### replaceGovernance

*Given:*

MAX_GUARDS = Constant - Maximum number of Guards who may vote on Proposed Strategies.
MIN_GUARDS = Contact - Minimum number of Guards which must exist for a Governance Contract change to even occur.

L<sub>GOV</sub>[MAX_GUARDS] = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.

Vault = address of Vault Contract which this contract provides governance over.

Votes = map of Guard addr -> Contract Addr for votes on Governance Contract for Vault

```mermaid
sequenceDiagram

    participant G as Governor
    participant C1 as Governance Contract
    participant V as Vault Contract
    participant N as Ethereum Network
    autonumber

    Note over G: NewGovernance = (address of new<br>Governance Contract)
    Note over V: Pre-Conditions:<br>GovernanceAddr = (addr of Governance Contract)    
    Note over C1: Pre-Conditions: <br>self.LGOV = (List of Current Guards)<br>MIN_GUARDS = (minimum number<br>of guards to change Governance)<br>self.Vault = (address of Vault Contract)<br>self.Votes = (map of Guards -> Addr)


    G->>C1: replaceGovernance(NewGovernance)

    Note over C1: Confirm there are enough Guards<br>to change Governance<br>len(self.LGOV >= MIN_GUARDS)
    Note over C1: Confirm self.sender is a Guard<br>msg.sender in self.LGOV
    Note over C1: Confirm NewGovernance is Different<br>NewConvernance != self<br>NewGovernance != ZERO_ADDRESS


    Note over C1: Record Guard's Vote<br>self.Votes[msg.sender] = NewGovernance

    
    Note over C1: See if we are unanimous<br>VoteCount = 0
    loop for each Governor in self.LGOV
        Note over C1: if self.Votes[Goveror] == NewGovernance: VoteCount += 1
    end

    C1-->>N: emit NewGovernanceVote(self.Vault, msg.Sender, NewGovernance, VoteCount, len(self.LGOV))

    alt if VoteCount == len(self.LGOV)
        C1->>V: replaceGovernance(NewGovernance)
    end


    Note over V: Confirm request is from current<br>Govenance Contract<br>confirm msg.sender = self.GovernanceAddr
    Note over V: Confirm NewGovernance is different<br>confirm NewGovernance != self.GovernanceAddr<br>confirm NewGovernance != ZERO_ADDRESS

        V-->>N: emit NewGovernanceContract(msg.Sender, self.GovernanceAddr, NewGovernance)

    Note over V: Update Governance Contract<br>self.GovernanceAddr = NewGovernance



    
```    
