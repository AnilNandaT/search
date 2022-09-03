import requests
import json
import os

url = os.environ.get('MODEL_URL')+'/v2/models/drug-search/infer' #API URL

def lambda_handler(event, context):
	msg = {}
	try:
		input_dict = json.loads(json.dumps(event))
		drug = input_dict['drug']
		filter1 = input_dict['filter1']
		pmids = input_dict['pmids']
		json_req = {
                    "inputs": [
                        {
                            "name": "input_text",
                            "shape": [
                                1,
                                1
                            ],
                            "datatype": "BYTES",
                            "data": [drug]
                        },
                        {
                            "name": "filter1",
                            "shape": [
                                1,
                                1
                            ],
                            "datatype": "BOOL",
                            "data": [filter1]
                        },
                        {
                            "name": "add_pmids1",
                            "shape": [
                                1,
                                1
                            ],
                            "datatype": "BOOL",
                            "data": [pmids]
                        }
                    ]
                    
                }
		x = requests.post(url, json=json_req)
		print('response from ')
		data = json.loads(x.text)
		msg.update({"code": x.status_code})
		if x.status_code == 200:
			msg.update({"result": json.loads(data['outputs'][0]['data'][0]) })
            return json.loads(json.dumps(msg, indent=4))
		else:
			msg.update({"result": ['Error']})
            raise Exception('Internal Error: Error getting inference from model')  
	except Exception as e:
        print(e)
		msg.update({"code":  0})
		msg.update({"result":  str(e)})
        raise Exception('Internal Error: Error getting inference from model') 
	# finally:
	# 	return json.loads(json.dumps(msg))
