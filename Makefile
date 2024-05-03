init: check-node-version
	rm -rf cache/* 
	rm -rf .build
	rm -rf node_modules
	pip install -r requirements.txt
	npm ci

test: check-node-version
	ape test -s
	ape test --network :mainnet-fork:hardhat -s

check-env:
ifndef WEB3_ALCHEMY_API_KEY
	$(error WEB3_ALCHEMY_API_KEY is undefined)
endif

LOCAL_VERSION := $(shell node --version | head -n 1)
REQUIRED_VERSION := v20.12.2


check-node-version:
ifeq ($(REQUIRED_VERSION), $(LOCAL_VERSION))
	@echo Correct node version detected, good job
else
	$(error Please install and use node $(REQUIRED_VERSION), you have $(LOCAL_VERSION))
endif


hardhat: check-env check-node-version
	npx hardhat node  --hostname 127.0.0.1 --port 8545 --fork https://eth-mainnet.g.alchemy.com/v2/${WEB3_ALCHEMY_API_KEY} --fork-block-number 17024800


abi-export:
	ape compile
	#Export ABI of contracts we expect frontends to use
	jq .abi .build/PendleAdapter.json  > ./abis/PendleAdapter.abi.json
	jq .abi .build/AdapterVault.json  > ./abis/AdapterVault.abi.json
	jq .abi .build/Governance.json  > ./abis/Governance.abi.json

