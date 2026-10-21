FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio==1.80.0 protobuf==6.33.6
COPY sdk/python/src ./sdk/python/src
COPY studies ./studies
COPY tools/launcher/runner.py ./tools/launcher/runner.py
ENV PYTHONPATH=/app/sdk/python/src:/app
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "tools/launcher/runner.py"]
