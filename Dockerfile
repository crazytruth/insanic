FROM python:3.6-alpine
# docker build --no-cache -t insanic -f build/Dockerfile.insanic .
LABEL maintainer crazytruth

ENV INSTALL_PATH /app
RUN mkdir -p $INSTALL_PATH

WORKDIR $INSTALL_PATH

ONBUILD ARG SERVICE
ONBUILD COPY requirements.txt /tmp

ONBUILD RUN apk add --update --no-cache --virtual .build-deps  \
        build-base gcc libffi-dev openssl-dev jpeg-dev && \
    pip install --upgrade \
    --index http://nexus.mmt.local:8081/repository/pypi/pypi \
    --index-url http://nexus.mmt.local:8081/repository/pypi/simple \
    --extra-index-url https://pypi.python.org/simple \
    --trusted-host nexus.mmt.local \
    -r /tmp/requirements.txt && \
    find /usr/local \
        \( -type d -a -name test -o -name tests \) \
        -o \( -type f -a -name '*.pyc' -o -name '*.pyo' \) \
        -exec rm -rf '{}' + && \
    runDeps="$( \
        scanelf --needed --nobanner --recursive /usr/local \
                | awk '{ gsub(/,/, "\nso:", $2); print "so:" $2 }' \
                | sort -u \
                | xargs -r apk info --installed \
                | sort -u \
    )" && \
    apk add --virtual .rundeps $runDeps && \
    apk del .build-deps && \
    rm -rf /var/cache/apk/* && \
    rm /tmp/requirements.txt && \
    adduser -D -u 1001 noroot

ONBUILD USER noroot

CMD ["/bin/sh"]