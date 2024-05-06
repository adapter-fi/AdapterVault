import os

import pytest

import boa


def forked_env_mainnet(block_id: int):
    alchemy_key = os.environ.get("WEB3_ALCHEMY_API_KEY")
    if alchemy_key == "":
        raise "WEB3_ALCHEMY_API_KEY must be provided"
    fork_uri =  "https://eth-mainnet.g.alchemy.com/v2/" + alchemy_key
    boa.env.fork(fork_uri, block_identifier=block_id)        
