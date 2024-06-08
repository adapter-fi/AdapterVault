#pragma version 0.3.10
#pragma evm-version cancun

struct SlippagePlan:
    percent: uint256
    qty: uint256 # zero means forever

struct SlippageExecution:
    plan_pos : uint256
    usage: uint256     
    val_in: uint256
    val_out: uint256

MAX_USAGE : constant(uint256) = 100
MAX_PLANS : constant(uint256) = 20

plans : public(DynArray[SlippagePlan, MAX_PLANS])
last_plan_pos : public(uint256)
plan_pos : public(uint256)
history : public(DynArray[SlippageExecution, MAX_USAGE])
history_pos : public(uint256)

@external
def __init__():
    self.plans = empty(DynArray[SlippagePlan, MAX_PLANS])
    self.last_plan_pos = 0
    self.plan_pos = 0
    self.history = empty(DynArray[SlippageExecution, MAX_USAGE])
    self.history_pos = 0


@external
def set_slippage(_percent: uint256, _qty: uint256 = 0):
    # _qty = 0 means keep on this one forever.
    plan : SlippagePlan = SlippagePlan({percent: _percent,
                                        qty: _qty})
    self.plans[self.last_plan_pos] = plan
    self.last_plan_pos += 1


@internal
def _update_plan_usage(_orig_val: uint256, _final_val: uint256, _plan: SlippagePlan):
    exec : SlippageExecution = self.history[self.history_pos]
    exec.plan_pos = self.plan_pos
    exec.usage += 1
    exec.val_in = _orig_val
    exec.val_out = _final_val

    if self.history_pos == 0:
        self.history[self.history_pos] = exec
    else:
        self.history[self.history_pos+1] = exec
    self.history_pos += 1

    # Once a SlippagePlan has a qty of zero it stays forever.
    # (Unless a slippage_result was requested before any plan was set.)
    if _plan.qty != 0:
        # There's a plan to track.
        if exec.usage == _plan.qty:
            # Next plan.
            self.plan_pos += 1


@external    
def slippage_result(_value : uint256) -> uint256:
    if len(self.plans) == 0:
        return _value
    plan : SlippagePlan = self.plans[self.plan_pos]
    result : uint256 = _value
    if plan.percent > 0:
        result = result * plan.percent / 100

    self._update_plan_usage(_value, result, plan)

    return result

