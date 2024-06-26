#pragma version 0.3.10
#pragma evm-version cancun

struct SlippagePlan:
    percent: decimal
    qty: uint256 # zero means forever

struct SlippageExecution:
    plan_pos : uint256
    usage: uint256     
    val_in: uint256
    val_out: uint256

MAX_USAGE : constant(uint256) = 100
MAX_PLANS : constant(uint256) = 20

plans : public(DynArray[SlippagePlan, MAX_PLANS])
plan_pos : public(uint256)
history : public(DynArray[SlippageExecution, MAX_USAGE])

@external
def __init__():
    self.plans = empty(DynArray[SlippagePlan, MAX_PLANS])
    self.plan_pos = 0
    self.history = empty(DynArray[SlippageExecution, MAX_USAGE])


@external
@view
def history_len() -> uint256:
    return len(self.history)


@external
def set_slippage(_percent: decimal, _qty: uint256 = 0):
    # _qty = 0 means keep on this one forever.
    plan : SlippagePlan = SlippagePlan({percent: _percent,
                                        qty: _qty})
    self.plans.append(plan)


@internal
def _update_plan_usage(_orig_val: uint256, _final_val: uint256, _plan: SlippagePlan):
    exec : SlippageExecution = empty(SlippageExecution)
    if len(self.history) > 0: 
        exec = self.history[len(self.history)-1]
    exec.plan_pos = self.plan_pos
    exec.usage += 1
    exec.val_in = _orig_val
    exec.val_out = _final_val

    self.history.append(exec)

    # Once a SlippagePlan has a qty of zero it stays forever.
    # (Unless a slippage_result was requested before any plan was set.)
    if _plan.qty != 0:
        # There's a plan to track.
        if exec.usage == _plan.qty:
            # Next plan.
            self.plan_pos += 1
            assert False, "NOT YET!"


@external    
def slippage_result(_value : uint256) -> uint256:
    #assert _value == 1000, "Not 1000!"
    if len(self.plans) == 0:
        return _value
    assert not self.plan_pos > len(self.plans), "Slippage txs exhausted!"     
    plan : SlippagePlan = self.plans[self.plan_pos]
    result : uint256 = _value
    if plan.percent > 0.0 and result > 0:
        loss : decimal = convert(result,decimal) * plan.percent / 100.0
        result -= convert(loss, uint256)
        #breakpoint()
        #assert False, "HERE!"

    self._update_plan_usage(_value, result, plan)

    return result

