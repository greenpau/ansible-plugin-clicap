#
# Build Docker image:     docker build -t greenpau/ansible-plugin-clicap-docs .
# Run Docker container:   docker run --rm -p 8000:8000 greenpau/ansible-plugin-clicap-docs
#

FROM alpine:latest
MAINTAINER Paul Greenberg @greenpau

RUN apk update && apk add lighttpd
COPY lighttpd.conf /etc/lighttpd/lighttpd.conf
COPY build/html/ /var/www/localhost/html
EXPOSE 8000
CMD ["/usr/sbin/lighttpd", "-D", "-f", "/etc/lighttpd/lighttpd.conf"]
