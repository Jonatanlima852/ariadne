# Imagem única para qualquer agente declarado em um scenario.py.
# O código do repositório é montado em tempo de execução; a imagem só traz
# o interpretador e as dependências do SDK (núcleo e extra LLM).
FROM python:3.12-slim
RUN pip install --no-cache-dir grpcio==1.80.0 protobuf==6.33.6 openai==2.50.0 pydantic==2.13.4
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "ariadne_sdk.worker"]
