FROM python:3.6-alpine3.7
LABEL maintainer crazytruth

ENV INSTALL_PATH /app
RUN mkdir -p $INSTALL_PATH

WORKDIR $INSTALL_PATH

ONBUILD ARG SERVICE
ONBUILD ARG ADDITIONAL_APK
ONBUILD COPY requirements.txt /tmp

ONBUILD ENV ADDITIONAL_APK=$ADDITIONAL_APK
ONBUILD RUN echo $ADDITIONAL_APK

RUN sed -i '1i http://alpine.msa.swarm/alpine/v3.7/community' /etc/apk/repositories \
    && sed -i '1i http://alpine.msa.swarm/alpine/v3.7/main' /etc/apk/repositories

RUN apk add --update --no-cache --virtual .build-deps  \
        build-base gcc libffi-dev jpeg-dev && \
    pip install --upgrade \
    --index http://nexus.mmt.local:8081/repository/pypi/pypi \
    --index-url http://nexus.mmt.local:8081/repository/pypi/simple \
    --extra-index-url https://pypi.python.org/simple \
    --trusted-host nexus.mmt.local \
    insanic && \
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
    rm -rf /var/cache/apk/*


ONBUILD RUN apk add --update --no-cache --virtual .build-deps  \
        build-base gcc libffi-dev jpeg-dev linux-headers $ADDITIONAL_APK && \
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