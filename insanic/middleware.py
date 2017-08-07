from sanic.log import log

# import opentracing

# MIDDLEWARE_CLASSES = (
#     'mmt_mk2.middleware.PinningRouterMiddleware',
#
#
#
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.locale.LocaleMiddleware',
#
#
#     'corsheaders.middleware.CorsMiddleware',
#
#
#
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
#     'oauth2_provider.middleware.OAuth2TokenMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
#     'django_requestlogging.middleware.LogSetupMiddleware',
#     'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
#     'django_user_agents.middleware.UserAgentMiddleware',
#
#
#
#     'mmt_mk2.middleware.MMTMobileApplicationMiddleware',
#     # 'mmt_mk2.middleware.MMTTargetedIndexMiddleware',
#     'mmt_mk2.middleware.MMTDisqusAuthCodeMiddleware',
#     'mmt_mk2.middleware.UserIpAddressMiddleware'
# )


# @app.middleware('request')
async def request_middleware(request):
    # log.debug("Request Middleware")
    # log.debug(request)
    # tracer = opentracing.tracer
    #
    # span_context = tracer.extract(
    #     format=opentracing.Format.HTTP_HEADERS,
    #     carrier=request.headers,
    # )
    # span = tracer.start_span(
    #     operation_name=request.operation,
    #     child_of(span_context))
    # span.set_tag('http.url', request.full_url)
    #
    # remote_ip = request.remote_ip
    # if remote_ip:
    #     span.set_tag(tags.PEER_HOST_IPV4, remote_ip)
    #
    # caller_name = request.caller_name
    # if caller_name:
    #     span.set_tag(tags.PEER_SERVICE, caller_name)
    #
    # remote_port = request.remote_port
    # if remote_port:
    #     span.set_tag(tags.PEER_PORT, remote_port)
    #
    # return span
    pass

async def response_middleware(request, response):
    # log.debug("Response Middleware")
    # log.debug(response)
    pass


# from opentracing import