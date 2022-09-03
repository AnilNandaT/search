from time import time

import requests
import json
import numpy as np


##global settings
url = 'http://localhost:8080/v2/models/drug-search/infer' #API URL
def call_api(ds1):
	json_req = {
    "inputs": [
        {
            "name": "input_text",
            "shape": [
                1,
                1
            ],
            "datatype": "BYTES",
            "data": ds1
        },
        {
            "name": "filter1",
            "shape": [
                1,
                1
            ],
            "datatype": "BOOL",
            "data": [True]
        },
        {
            "name": "add_pmids1",
            "shape": [
                1,
                1
            ],
            "datatype": "BOOL",
            "data": [True]
        }
    ]

}

	x = requests.post(url, json=json_req)
	if x.status_code == 200:
		return x.text, x.status_code
	else:
		return [], x.status_code

def compute_drug_protein(ds1):
	try:
		msg = {}
		# try:
		model_output, status_code = call_api(ds1)
		data = json.loads(model_output)
		x = json.loads(data["outputs"][0]["data"][0])
		msg.update({"code": status_code})
		msg.update({"result": x})
	except Exception as e:
		msg.update({"code": 0})
		msg.update({"result": str(e)})
		msg.update(x)
	finally:
		return json.dumps(msg, indent=4)


if __name__ == "__main__":
	data = ["covid"]
	start = time()
	prg_output = compute_drug_protein(data)
	resp_size = len(prg_output.encode())
	print(data)
	for k, v in sorted(list(json.loads(prg_output)["result"]["drugs"].items()), reverse=True, key=lambda x: x[1]["metrics"]["F-0.5"]):
		print(k)
		print(v["metrics"]["F-0.5"], v["metrics"]["sentiment"])
	# print("Output result keys: ", json.loads(prg_output)["result"]["drugs"].keys())
	# print("Output result keys: ", .keys())
	print("Request time: {:.2f}".format(time() - start))
	print("Resp size: ", resp_size)
