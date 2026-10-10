FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio==1.80.0 protobuf==6.33.6
COPY sdk/python/src ./sdk/python/src
COPY scenarios ./scenarios
COPY examples/demo_scenario ./examples/demo_scenario
COPY studies ./studies
COPY benchmarks/logistics.py ./benchmarks/logistics.py
COPY scripts/launcher/runner.py ./scripts/launcher/runner.py
ENV PYTHONPATH=/app/sdk/python/src:/app
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "scripts/launcher/runner.py"]
