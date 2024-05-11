import boa

def test_transient():
    cont = boa.loads("""
#pragma version 0.3.10
#pragma optimize codesize
#pragma evm-version cancun
cache: transient(uint256)
              
@external
def __init__():
    pass

@external
@nonpayable
def set(num: uint256):
    self.cache = num

@external
@nonpayable
def get() -> uint256:
    return self.cache
            """)
    
    assert cont.get() == 0
    cont.set(100)
    assert cont.get() == 0
