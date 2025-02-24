FROM python:3.8.10

ENV PYTHONUNBUFFERED True

ENV APP_HOME /app
ENV PORT 5000

WORKDIR $APP_HOME

COPY . ./

RUN pip install --no-cache-dir -r requirements.txt

# CMD [ "python", "app.py" ]
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 src.__main__:app
