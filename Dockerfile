FROM nvcr.io/nvidia/tritonserver:22.05-py3
RUN pip install --upgrade pip
RUN mkdir -p /src
COPY ./requirements.txt /src
RUN pip install -r /src/requirements.txt
COPY src /src
COPY data/ /src/data/
RUN ls -la /src/data/ 
COPY models /models
WORKDIR /
CMD ["tritonserver", "--model-repository=/models", "--allow-grpc=false", "--allow-http=true", "--http-port=8080", "--allow-metrics=false", "--allow-gpu-metrics=false"]
