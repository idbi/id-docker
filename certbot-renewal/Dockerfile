FROM python:3.12.16-alpine3.24

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup -S -g 10001 certbot-renewal \
    && adduser -S -D -H -u 10001 -G certbot-renewal certbot-renewal \
    && mkdir -p /app /etc/letsencrypt /var/lib/letsencrypt \
    && chown -R certbot-renewal:certbot-renewal \
        /app /etc/letsencrypt /var/lib/letsencrypt

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement /app/requirements.txt

COPY certbot_renewal.py /app/certbot_renewal.py

USER certbot-renewal

ENTRYPOINT ["python", "-m", "certbot_renewal"]
