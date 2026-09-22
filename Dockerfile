FROM python:3.12-slim
WORKDIR /code

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 5000

# One worker, many threads: the outgoing rate gate in app.py is per-process,
# and the work is IO-bound anyway.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "60", "app:app"]
