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
    boa.env.time_travel(seconds=1200)
    #re issue https://github.com/vyperlang/titanoboa/issues/218
    #this test broken in boa..
    assert cont.get() == 0
