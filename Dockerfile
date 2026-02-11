FROM python:3.13-alpine

WORKDIR /code

ENV TZ=America/Toronto

RUN pip install --no-cache-dir \
   pandas requests python-dateutil "fastapi[standard]" uvicorn fredapi

COPY . /code