FROM python:3.12-slim
WORKDIR /app
# ca-certificates : indispensable pour les appels HTTPS via urllib (API Anthropic dans grader.py)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 8 -r requirements.txt
COPY *.py ./
COPY *.json ./
EXPOSE 8000
# Import idempotent (upsert) des cartes au demarrage : garantit que la base du
# volume /data contient les cartes apres chaque (re)deploiement, sans shell manuel.
# Port = $PORT si fourni (Railway), sinon 8000 (local).
CMD ["sh", "-c", "python import_cards.py cards.json || true; python import_cards.py cards.timeseries.json || true; python import_exams.py ts_exams.json || true; python fix_no_audit.py || true; exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
