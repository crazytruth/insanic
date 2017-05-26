from sanic.log import log

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
    pass

async def response_middleware(request, response):
    # log.debug("Response Middleware")
    # log.debug(response)
    pass
