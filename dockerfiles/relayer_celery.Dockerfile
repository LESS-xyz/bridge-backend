FROM python:3.8

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

COPY . /app
CMD ["celery", "-A", "relayer_celery", "worker", "-B", "--loglevel=info"]