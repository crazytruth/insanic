# from insanic.conf import settings
# from insanic.tracing.sampling import Sampler
# from insanic.responses import json_response
# from insanic.views import InsanicView
#
#
# class TestSampler:
#
#     def test_sampler_init(self, insanic_application):
#         sampler = Sampler(insanic_application)
#         assert sampler.app == insanic_application
#
#     def test_sample_tracing_service_name(self, insanic_application):
#         sampler = Sampler(insanic_application)
#
#         assert settings.MMT_ENV in sampler.tracing_service_name
#         assert settings.SERVICE_NAME in sampler.tracing_service_name
#
#     def test_sampling_on_tracing_enabled_false(self, insanic_application):
#         sampler = Sampler(insanic_application)
#
#         assert settings.TRACING_ENABLED is False
#
#         rules = sampler.sampling_rules
#
#         assert rules['default']['fixed_target'] is 0
#         assert rules['default']['rate'] is 0
#         assert rules['rules'] == []
#
#     def test_sampling_on_tracing_enabled_true(self, insanic_application, monkeypatch):
#         monkeypatch.setattr(settings, 'TRACING_ENABLED', True)
#
#         assert settings.TRACING_ENABLED is True
#
#         sampler = Sampler(insanic_application)
#
#         rules = sampler.sampling_rules
#
#         assert rules['default']['fixed_target'] is settings.DEFAULT_SAMPLING_FIXED_TARGET
#         assert rules['default']['rate'] is settings.DEFAULT_SAMPLING_RATE
#
#     def test_no_sampling_rate_on_view(self, insanic_application, monkeypatch):
#         monkeypatch.setattr(settings, 'TRACING_ENABLED', True)
#         assert settings.TRACING_ENABLED is True
#
#         class MockView(InsanicView):
#
#             def get(self, request, *args, **kwargs):
#                 return json_response({})
#
#         insanic_application.add_route(MockView.as_view(), "/hello")
#
#         sampler = Sampler(insanic_application)
#
#         rules = sampler.sampling_rules
#
#         assert len(rules['rules']) is 0
