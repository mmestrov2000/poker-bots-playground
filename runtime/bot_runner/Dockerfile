FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /opt/bot

COPY requirements.txt /opt/bot/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bot_server.py /opt/bot/bot_server.py
COPY bot /opt/bot/bot

ENV BOT_DIR=/opt/bot/bot
EXPOSE 8080

CMD ["python", "/opt/bot/bot_server.py"]
