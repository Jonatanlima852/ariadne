FROM python:3.11-slim
WORKDIR /app

RUN pip install --no-cache-dir grpcio openai pydantic protobuf

COPY sdk/python ./sdk/python
RUN pip install --no-cache-dir --no-deps --no-build-isolation ./sdk/python

COPY studies/agents/planner-explainer/ ./
COPY studies ./studies

CMD ["python", "main.py"]
