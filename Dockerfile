FROM debian:stretch-slim

COPY src/* /

RUN apt-get update \
    && apt-get install caffe-cpu python3 python3-pip python3-dev python3-setuptools wget -y --no-install-recommends \
    && pip3 install wheel \
    && pip3 install -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

CMD ["python3", "main.py"]