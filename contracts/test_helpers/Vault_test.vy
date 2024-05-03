#pragma version 0.3.10

event PoolRebalance:
    newStrategy: Strategy

event NewGovernanceContract:
    NewGovernance: address

struct Strategy:
    Nonce: uint256
    ProposerAddress: address
    Weights: DynArray[uint256, MAX_ADAPTERS]
    APYNow: uint256
    APYPredicted: uint256
    TSubmitted: uint256
    TActivated: uint256
    Withdrawn: bool
    no_guards: uint256
    VotesEndorse: DynArray[address, MAX_GUARDS]
    VotesReject: DynArray[address, MAX_GUARDS]

MAX_GUARDS: constant(uint256) = 2
MAX_ADAPTERS: constant(uint256) = 10
GovernanceAddress: public(address)
contractOwner: public(address)

@external
def __init__(contractOwner: address):
    self.contractOwner = contractOwner

@external
def PoolRebalancer(newStrategy: Strategy):
    log PoolRebalance(newStrategy)

@external
def replaceGovernanceContract(NewGovernance: address):
    log NewGovernanceContract(NewGovernance)
