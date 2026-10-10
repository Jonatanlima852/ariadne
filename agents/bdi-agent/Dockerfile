FROM python:3.11-slim
WORKDIR /app

RUN pip install --no-cache-dir grpcio protobuf

COPY sdk/python ./sdk/python
RUN pip install --no-cache-dir --no-deps --no-build-isolation ./sdk/python

# copia o código do agente (beliefs, plans e o agente em si)
COPY agents/bdi-agent/beliefs.py .
COPY agents/bdi-agent/plans.py .
COPY agents/bdi-agent/main.py .
COPY studies ./studies

CMD ["python", "main.py"]
