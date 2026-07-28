FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --shell /bin/bash appuser

RUN chown -R appuser:appuser /app

USER appuser

RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "CoreAPI.wsgi:application", "--bind", "0.0.0.0:8000"]