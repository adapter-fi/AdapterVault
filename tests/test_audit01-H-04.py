"""
## [H-04] Dangerous approval/rejection criteria when number of guards is odd

### Details 

[Governance.vy#L310](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/Governance.vy#L310)

    assert (len(pending_strat.VotesEndorse) >= len(self.LGov)/2) or \

The above assert statement requires that the number of endorsements equals or exceeds the number of guards / 2. This becomes an issue with odd numbers due to truncation. If you were to have 3 guards then even a single approval would allow instant approval ( 3/2 = 1). In this scenario even a single malicious or compromised guard could drain the entire vault via a malicious proposal.

### Lines of Code

[Governance.vy#L291-L324](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/Governance.vy#L291-L324)

### Recommendation

Make the requirement that it must equal or exceed length / 2 + length % 2

"""
import ape
from tests.conftest import ensure_hardhat, prompt
import pytest
from  pytest import raises

#from .test_Governance import owner, governance_contract, dai, funds_alloc, vault_contract_one
from .test_Governance import WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED

STRATEGY = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED)

# MUST match Governance.vy MAX_GUARDS
MAX_GUARDS = 5

@pytest.fixture
def owner(project, accounts):
    owner = accounts[0]
    return owner

@pytest.fixture
def dai(project, owner, accounts):
    ua = owner.deploy(project.ERC20, "DAI", "DAI", 18, 0, owner)
    return ua


@pytest.fixture
def funds_alloc(project, owner):
    f = owner.deploy(project.FundsAllocator)
    return f

@pytest.fixture
def governance_contract(owner, project, accounts):

    owner, operator, someoneelse, someone, newcontract, currentvault = accounts[:6]

    # deploy the contract with the initial value as a constructor argument

    gcontract = owner.deploy(project.Governance, owner, 21600)

    return gcontract      

@pytest.fixture
def vault_contract_one(governance_contract, owner, project, accounts, dai, funds_alloc):

    owner, operator, someoneelse, someone, newcontract, currentvault, currentgovernance = accounts[:7]

    vcontractone = owner.deploy(project.AdapterVault, "TestVault Token", "TEST", 18, dai, [], governance_contract, funds_alloc, "2.0")

    return vcontractone


def test_endorsement_short_circuit(governance_contract, vault_contract_one, accounts, owner):
    strat = accounts[1]
    g1 = accounts[2]
    guards = accounts[2:MAX_GUARDS-1]
    
    governance_contract.addVault(vault_contract_one, sender=owner)

    # Can't add a strategy without a guard.
    with ape.reverts():
        governance_contract.submitStrategy(STRATEGY, vault_contract_one, sender=strat)

    # Setup for test.
    governance_contract.addGuard(g1, sender=owner)
    Guards = 1

    for i in guards:

        receipt = governance_contract.submitStrategy(STRATEGY, vault_contract_one, sender=strat)
        nonce = receipt.return_value


        Endorsements = 0
        for v, g in enumerate(guards):

            governance_contract.endorseStrategy(nonce, vault_contract_one, sender=guards[v])
            Endorsements += 1

            if Endorsements < Guards // 2 + 1:
                with ape.reverts("Premature activation with insufficience endorsements."):
                    governance_contract.activateStrategy(nonce, vault_contract_one, sender=strat)

            else:
                governance_contract.activateStrategy(nonce, vault_contract_one, sender=strat)

                # for old_guard in guards[:v+1]:
                #     governance_contract.removeGuard(old_guard)

                #governance_contract.withdrawStrategy(nonce, vault_contract_one, sender=strat)
                ape.chain.pending_timestamp += 100000
                break

        # Add another guard.
        if i != guards[-1]:
            governance_contract.addGuard(guards[v+1], sender=owner)
            Guards += 1

