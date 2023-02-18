FROM python:3.11

WORKDIR /src
ADD . /src
RUN pip install .
CMD ["python", "-m", "dundercode"]
