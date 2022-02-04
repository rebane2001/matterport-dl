FROM python:3.10.1
WORKDIR /matterport-dl

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY docker-entrypoint.sh docker-entrypoint.sh
COPY graph_posts graph_posts
COPY matterport-dl.py matterport-dl.py

CMD [ "/bin/sh", "docker-entrypoint.sh" ]
