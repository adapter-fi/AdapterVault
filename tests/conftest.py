import pytest
from ape import chain
import json, requests, os

@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


def is_not_hard_hat():
    try:
        print("Current chain id is: %s." % chain.chain_id)
        return chain.chain_id!=1
    except ape.exceptions.ProviderNotConnectedError:
        print("Alert: Not connected to a chain.")
        return True

@pytest.fixture
def ensure_hardhat():
    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")
    #reset hardhat
    #hardcoding here, not good.
    #TODO: figure out how to copy from apt-config.yaml
    reset_hardhat_fork(17024800)

def reset_hardhat_fork(block):
    reset_request = {"jsonrpc": "2.0", "method": "hardhat_reset", "id": 1,
        "params": [{
            "forking": {
                "jsonRpcUrl": "https://eth-mainnet.alchemyapi.io/v2/"+os.getenv('WEB3_ALCHEMY_API_KEY'),
                "blockNumber": block
            }
        }]}
    requests.post("http://localhost:8545/", json.dumps(reset_request))


def pytest_addoption(parser):
    parser.addoption(
        '--prompt', action='store', default=False, help='Prompt between runs'
    )

@pytest.fixture
def prompt(request):
    return request.config.getoption('--prompt')


# @pytest.fixture(scope="session")
# def receiver(accounts):
#     return accounts[1]


# # @pytest.fixture(scope="session")
# # def ProposedStrategy()


# @pytest.fixture(scope="session")
# def token(owner, project):
#     return owner.deploy(project.Token)


# @pytest.fixture(scope="session")
# def ZERO_ADDRESS() -> str:
#     """
#     Zero / Null Address
#     https://consensys.github.io/smart-contract-best-practices/development-recommendations/token-specific/zero-address/

#     Returns:
#         "0x0000000000000000000000000000000000000000"
#     """
#     return "0x0000000000000/000000000000000000000000000"


  
    