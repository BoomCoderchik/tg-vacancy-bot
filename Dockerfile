FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY tg_vacancy_bot ./tg_vacancy_bot

RUN pip install --no-cache-dir .
RUN mkdir -p /app/data

CMD ["tg-vacancy-bot", "run-web"]
