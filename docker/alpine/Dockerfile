FROM alpine:latest
MAINTAINER Paul Greenberg @greenpau

RUN apk update && apk add python curl && \
    mkdir -p /usr/local/src/pip && cd /usr/local/src/pip && \
    curl -s https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python get-pip.py

RUN apk update && apk add expect openssh-client build-base python-dev libffi-dev openssl-dev && \
    pip install ansible==2.1.0.0 && \
    apk del build-base python-dev libffi-dev openssl-dev

RUN apk add vim

WORKDIR /etc/ansible

COPY demo/firewall/ssh.config /root/.ssh/config
COPY demo/firewall/ssh.proxy.rsa /root/.ssh/id_rsa
COPY demo/firewall/ssh.proxy.rsa.pub /root/.ssh/id_rsa.pub
COPY demo/firewall/myvault.yml /root/.clicap.vault.yml
COPY demo/firewall/vault.passwd /root/.vault.passwd
COPY demo/firewall/hosts /etc/ansible/
COPY demo/firewall/playbooks/*.yml /etc/ansible/playbooks/
COPY demo/firewall/files/clicap/spec/*.yml /etc/ansible/files/clicap/spec/
COPY demo/firewall/files/clicap/os/*.yml /etc/ansible/files/clicap/os/
COPY demo/firewall/files/clicap/host/*.yml /etc/ansible/files/clicap/host/
COPY demo/firewall/files/clicap/exceptions.yml /etc/ansible/files/clicap/
COPY dist/ansible-plugin-clicap-0.4.tar.gz /usr/local/src/
RUN  pip install /usr/local/src/ansible-plugin-clicap-0.4.tar.gz

ENTRYPOINT ["/bin/sh"]
