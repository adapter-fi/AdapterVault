## Installation & Smoke Test

### Prerequisites:

1. Signup for free [alchemy account](https://www.alchemy.com/), create a project with ETH mainnet.
2. export your API key: `export WEB3_ALCHEMY_API_KEY=api_key`
3. Ensure that nvm is installed for node deployments. And you are running 20.x lts: `nvm install v20.12.2` and `nvm use v20.12.2`
4. Create a python virtual environment to isolate your project.

### Initialization

1. Activate your python virtual environment.
2. Install all environmental dependencies: `make init`

### Running hardhat node

Currently you have to run the hardhat node yourself instead of letting ape run it due to some configuration issues.

1. In a separate tab (remember check node versions in this new tab and WEB3_ALCHEMY_API_KEY): `make hardhat`

### Smoke Test

1. Execute the unit tests: `./runtests`

If all your tests pass then you're good to go.


#### Dealing with Issues

Confirm node is correct. Most problems are due to node.
```
$ node --version
v20.12.2
```

Make sure nothing is listening on port 8445.

```
sudo netstat -lntp | grep 8545
```

Ensure hardhat is running (see instructions above)

#### Now in another shell:

```
./runtests
```



## Test & Execution Environment 

We're using [ApeWorX](https://github.com/ApeWorX) with [PyTest](https://github.com/pytest-dev/pytest) as our development environment.

[ApeWorX Discord](https://discord.gg/apeworx)

[ApeWorX Website](https://www.apeworx.io/)

[ApeWorX Documentation](https://docs.apeworx.io/ape/stable/)

[PyTest Website](https://pytest.org)


