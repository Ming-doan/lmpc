FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*
RUN pip install uv
WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system -e .
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
