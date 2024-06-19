## Installation & Smoke Test

### Prerequisites:

1. Signup for free [alchemy account](https://www.alchemy.com/), create a project with ETH mainnet.
2. export your API key: `export WEB3_ALCHEMY_API_KEY=api_key`
3. Ensure that nvm is installed for node deployments. And you are running 20.x lts: `nvm install v20.12.2` and `nvm use v20.12.2`
4. Create a python virtual environment to isolate your project.

### Initialization

1. Activate your python virtual environment.
2. Install all environmental dependencies: `make init`

### Smoke Test

1. Execute the unit tests: `make test`

If all your tests pass then you're good to go.


## Test & Execution Environment 

We're using [Titanoboa](https://github.com/vyperlang/titanoboa) with [PyTest](https://github.com/pytest-dev/pytest) as our development environment.

[Titanoboa Discord](https://discord.com/channels/969926564286459934/990983542680993802)

[Titanoboa Documentation](https://titanoboa.readthedocs.io/en/latest/)

[PyTest Website](https://pytest.org)


