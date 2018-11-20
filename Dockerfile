FROM debian:stretch-slim

COPY src/* /

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    caffe-cpu \
    python3 \
    python3-dev \
    python3-numpy \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    && pip3 install -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

CMD ["python3", "main.py"]