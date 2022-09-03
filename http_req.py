import requests
import json
import numpy as np
from time import time


##global settings
url = 'http://localhost:8080/v2/models/drug-search/infer' #API URL
def call_api(query):
	json_req = {
    "inputs": [
        {
            "name": "input_text",
            "shape": [
                1,
                1
            ],
            "datatype": "BYTES",
            "data": [query]
        },
        {
            "name": "filter1",
            "shape": [
                1,
                1
            ],
            "datatype": "BYTES",
            "data": [True]
        },
        {
            "name": "add_pmids1",
            "shape": [
                1,
                1
            ],
            "datatype": "BYTES",
            "data": [True]
        }
    ]

}
	start = time()
	x = requests.post(url, json=json_req)
	print(time() - start)
	if x.status_code == 200:
		return x.text, x.status_code
	else:
		return [], x.status_code

def compute_drug_protein(ds1):
	msg = {}
	try:
		model_output, status_code = call_api(ds1)
		data = json.loads(model_output)
		x = json.loads(data['outputs'][0]['data'][0])

		msg.update({"code": status_code})
		msg.update(x)
	except Exception as e:
		msg.update({"code":  0})
		msg.update({"result":  str(e)})
	finally:
	 	return json.dumps(msg, indent=4)

if __name__ == "__main__":
	query = "covid virus"
	prg_output = compute_drug_protein(query)
	print(prg_output)
