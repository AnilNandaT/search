import json
import os
import numpy as np
from triton_python_backend_utils import get_input_tensor_by_name, Tensor, get_output_config_by_name, triton_string_to_numpy, InferenceResponse, TritonError
from src.search.search import SearchEngine
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
# takes a long time to load
se = SearchEngine()


class Drug_Search:
    def __init__(self) -> None:
        super().__init__()
    def processit(self, input_text, filter1, add_pmids):
        lst = []
        for counter in range(input_text.shape[0]):
            text = input_text[counter]
            my_text = text[0].decode("utf-8")
            result = se.search(my_text, do_filter=bool(filter1[counter][0]),add_pmids_for_each_item=bool(add_pmids[counter][0]))
            lst.append(json.dumps(result))
        return lst # to return a list
class TritonPythonModel:
    def __init__(self) -> None:
        super().__init__()
        self.model_config = None
        self.result_dtype = None
        self.ds_model = Drug_Search()
    # def initialize(self, args):
    #     self.model_config = model_config = json.loads(args['model_config'])
    #     out_config_result = get_output_config_by_name(model_config, "output_text")
    #     self.result_dtype = triton_string_to_numpy(out_config_result['data_type'])
    def execute(self, requests):
        responses = []    
        ds_model = self.ds_model
        for request in requests:
            input_text = get_input_tensor_by_name(request, "input_text")
            filter1 = get_input_tensor_by_name(request, "filter1")
            add_pmids1 = get_input_tensor_by_name(request, "add_pmids1")
            result_txt = ds_model.processit(input_text.as_numpy(),filter1.as_numpy(),add_pmids1.as_numpy())
            tensor_result = Tensor("model_output", np.array(result_txt,dtype=np.bytes_))
            #tensor_result_xml = Tensor("output_xml", np.array(result_xml,dtype=np.bytes_))
            inference_response = InferenceResponse(output_tensors=[tensor_result])
            responses.append(inference_response)
            return responses