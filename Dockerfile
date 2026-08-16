FROM python:3.12-slim

# fonts-dejavu-core stays in the image: the OG quote cards are typeset with it.
RUN apt update; apt install -y git gcc fonts-dejavu-core
WORKDIR /src
ADD . /src
RUN pip install .
RUN apt remove git gcc; apt autoremove
CMD ["python", "-m", "dundercode"]
