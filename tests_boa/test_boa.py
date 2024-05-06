import boa, os, pytest

from boa.environment import Env

# run all tests with this forked environment
# called as fixture for its side effects
@pytest.fixture(scope="function")
def forked_env():
    with boa.swap_env(Env()):
        fork_uri = os.environ.get("MAINNET_ENDPOINT") or "http://localhost:8545"
        block_id = 18801970  # some block we know the state of
        boa.env.fork(fork_uri, block_identifier=block_id)
        yield

def test_boa(forked_env):
    assert boa.eval("empty(uint256)")==0
