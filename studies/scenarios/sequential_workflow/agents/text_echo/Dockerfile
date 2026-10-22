FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir grpcio protobuf
COPY sdk/python/src ./sdk/python/src
COPY studies ./studies
ENV PYTHONPATH=/app/sdk/python/src:/app
CMD ["python", "-m", "studies.scenarios.sequential_workflow.agents.text_echo.main"]
