FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir requests
COPY setup_alerts_api.py .
ENV PYTHONUNBUFFERED=1
CMD ["python", "setup_alerts_api.py"]
