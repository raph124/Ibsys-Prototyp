FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sensor_realistic.py .
ENV PYTHONUNBUFFERED=1
CMD ["python", "sensor_realistic.py"]