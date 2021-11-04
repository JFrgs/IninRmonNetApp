from ubuntu:18.04
LABEL maintainer "luka.korsic@iinstitute.eu"

# Install dependencies
WORKDIR /app/
COPY requirements.txt /app/
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && mkdir -p /usr/share/man/man1 && mkdir -p /usr/share/man/man7  && \
    apt-get -y install apt-utils python3-dev python3-apt python3-pip iputils-ping wget curl ntpdate iproute2 net-tools && \
    pip3 install -r requirements.txt

# Get rMON NetApp libraries
WORKDIR /app/
COPY src/*.py /app/
COPY src/lib/* /app/lib/
COPY entrypoint.sh /app/

# Run rMON NetApp
# ENTRYPOINT ["python3", "/app/NetApp.py"]
