FROM python:3.11-slim
WORKDIR /app
COPY sdk/python/pyproject.toml ./sdk/python/pyproject.toml
COPY sdk/python/src ./sdk/python/src
RUN pip install --no-cache-dir './sdk/python[llm]'
COPY studies ./studies
ENV PYTHONPATH=/app
CMD ["python", "-m", "studies.scenarios.logistics.v2.agents.order_interpreter.main"]
