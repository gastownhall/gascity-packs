FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/gascity-rlm

COPY requirements.lock /opt/gascity-rlm/requirements.lock
RUN python -m pip install --upgrade pip \
    && python -m pip install --require-hashes -r /opt/gascity-rlm/requirements.lock

COPY scripts /opt/gascity-rlm/scripts

ENTRYPOINT ["python", "/opt/gascity-rlm/scripts/rlm_runner.py"]
