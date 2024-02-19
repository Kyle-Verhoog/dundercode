FROM python:3.12-slim

RUN apt update; apt install -y git gcc
WORKDIR /src
ADD . /src
RUN pip install .
RUN apt remove git gcc; apt autoremove
CMD ["python", "-m", "dundercode"]
