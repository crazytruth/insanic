FROM python:3.6-alpine
# docker build --no-cache -t insanic -f build/Dockerfile.insanic .
LABEL maintainer crazytruth

ENV INSTALL_PATH /app
RUN mkdir -p $INSTALL_PATH

WORKDIR $INSTALL_PATH

ONBUILD ARG SERVICE
ONBUILD COPY $SERVICE/requirements.txt /tmp

ONBUILD RUN apk add --update --no-cache --virtual .build-deps  \
        build-base gcc libffi-dev openssl-dev libjpeg-dev && \
    pip install --upgrade --extra-index-url http://pypi.mmt.local/ --trusted-host pypi.mmt.local -r /tmp/requirements.txt && \
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