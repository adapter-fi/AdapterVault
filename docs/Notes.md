
LP_UNIQUENESS

Adapters, in their present implementation, are stateless and hold no assets. Any shares provided by the underlying LP are credited towards the Dynamo4626 that the Adapter belongs to. The Dynamo4626 contract determines its total assets by iterating over each Adapter and summing the value of its shares.

For this reason, we must NEVER allow an LP to be accessed through more than one Adapter otherwise the Dynamo4626 will count its LP shares for each time its iterated over.

Motivations for this design decision included:
	1. We need to implement security at adapter. 
	2. Might add another transfer/approval hop for deposit/withdraw. (unlikely in most circumstances)
	3. Not great UX if investor can't see all backing tokens belonging to the vault contract. 
	4. Changing adapter would mean transferring all the lp tokens to new one.

TRUST_POOL_BALANCES

We have to assume get_pool_balances is correct!!