FROM python:3.11-slim
WORKDIR /app

# instala grpcio diretamente (sem uv, que é ferramenta de dev)
RUN pip install --no-cache-dir grpcio protobuf

# copia os stubs gerados pelo protoc e o ariadne_sdk
COPY sdk/python/src ./sdk/python/src

# copia o código do agente
COPY studies/agents/failing-agent/main.py .

ENV PYTHONPATH=/app/sdk/python/src

CMD ["python", "main.py"]
