import os

import pytest

import boa
from boa.environment import Env


# run all tests with this forked environment
# called as fixture for its side effects
@pytest.fixture(scope="module", autouse=True)
def forked_env_mainnet():
    with boa.swap_env(Env()):
        alchemy_key = os.environ.get("WEB3_ALCHEMY_API_KEY")
        if alchemy_key == "":
            raise "WEB3_ALCHEMY_API_KEY must be provided"
        fork_uri =  "https://eth-mainnet.g.alchemy.com/v2/" + alchemy_key
        block_id = 17024800  # some block we know the state of
        boa.env.fork(fork_uri, block_identifier=block_id)
        yield
