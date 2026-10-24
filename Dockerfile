FROM python:3.12-slim

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir . fastapi uvicorn

EXPOSE 8000
CMD ["uvicorn", "jobs_api:app", "--host", "0.0.0.0", "--port", "8000"]
