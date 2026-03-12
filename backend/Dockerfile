FROM python:3.11.7-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache vim python3 py3-pip curl

COPY . /app

RUN rm -rf .env

# install dependencies
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

RUN chmod +x entrypoint.sh

EXPOSE 8002

ENTRYPOINT ["/app/entrypoint.sh"]
