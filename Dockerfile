FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TZ=Asia/Jakarta
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
EXPOSE 8000
# di belakang reverse proxy (Caddy/Nginx); port 8000 hanya dibuka ke 127.0.0.1 oleh compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
