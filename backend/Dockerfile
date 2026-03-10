FROM python:3.11.7-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add vim python3 py3-pip

COPY . /app

RUN rm -rf .env

# install dependencies
RUN apk add --virtual .build-deps gcc musl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps


EXPOSE 8002
# # Default: run ASGI server with gunicorn + uvicorn workers
# CMD ["gunicorn", "assured_express.asgi:application", \
#      "-k", "uvicorn.workers.UvicornWorker", \
#      "--bind", "0.0.0.0:8000", \
#      "--workers", "3", \
#      "--timeout", "120", \
#      "--access-logfile", "-"]
