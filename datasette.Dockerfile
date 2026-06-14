FROM python:3.11-slim

RUN pip install datasette

WORKDIR /data

CMD ["datasette", "/app/data/deals.db", "-h", "0.0.0.0", "-p", "8001"]