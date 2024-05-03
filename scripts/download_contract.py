#download a contract from etherscan...need to provide apikey

import requests, json, os, sys

CONTRACT=sys.argv[1]
API_KEY = os.environ["ETHERSCAN_API_KEY"]
OUT_DIR=sys.argv[2]

if "__main__" in __name__:
    print("gi")
    url = "https://api.etherscan.io/api?module=contract&action=getsourcecode&address=" + CONTRACT + "&apikey=" + API_KEY
    print(url)
    resp = requests.get(url)
    ret = resp.json()
    blob = json.loads(ret["result"][0]["SourceCode"][1:-1])["sources"]
    for fname in blob:
        path = os.path.join(OUT_DIR, fname)
        print(path)
        print("\n\n")
        # print(blob[fname]["content"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(blob[fname]["content"])

