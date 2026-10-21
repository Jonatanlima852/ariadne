FROM python:3.12-slim

WORKDIR /app

COPY tools/clients/submit-task/pyproject.toml ./
RUN pip install --no-cache-dir grpcio protobuf

COPY tools/clients/submit-task/main.py ./main.py
COPY sdk/python/src/contract /sdk/contract

ENV PYTHONPATH=/sdk
ENV ORCHESTRATOR_ADDR=orchestrator:50052

ENTRYPOINT ["python", "main.py"]
