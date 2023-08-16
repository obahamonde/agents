FROM python:3.9.7-slim-buster

WORKDIR /app

COPY requirements.txt requirements.txt

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn","-k","aiohttp.GunicornWebWorker","-b","0.0.0.0:8080","main:app","--reload"]
