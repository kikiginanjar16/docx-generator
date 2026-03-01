FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY .env.example ./.env.example
COPY sample_request.json ./sample_request.json

EXPOSE 8293

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8293"]
