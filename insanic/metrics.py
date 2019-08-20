from prometheus_client import Gauge, Counter, Info, core


class PrometheusMetric(object):
    def __init__(self, metric_type, name, documentation, **kwargs):
        self.metric_type = metric_type
        self.name = name
        self.documentation = documentation
        self.kwargs = kwargs
        self._value = self.metric_type(self.name, self.documentation, **self.kwargs)

    def __get__(self, obj, objtype):
        return self._value

    def reset(self):
        self._value = self.metric_type(self.name, self.documentation, **self.kwargs)


class InsanicMetrics(object):
    registry = core.REGISTRY

    TOTAL_TASK_COUNT = PrometheusMetric(Gauge, 'total_task_count',
                                        'Number of tasks not yet finished.')

    ACTIVE_TASK_COUNT = PrometheusMetric(Gauge, 'active_task_count',
                                         'Number of tasks that are not done.')
    PROC_RSS_MEM_BYTES = PrometheusMetric(Gauge, 'proc_rss_mem_bytes',
                                          'Memory in bytes the process is using.')

    PROC_RSS_MEM_PERC = PrometheusMetric(Gauge, 'proc_rss_mem_perc',
                                         'Percentage of Memory the process is using.')

    PROC_CPU_PERC = PrometheusMetric(Gauge, 'proc_cpu_perc',
                                     'Percentage of CPU currently in use.')
    REQUEST_COUNT = PrometheusMetric(Counter, 'request_count',
                                     'The number of requests this application has handled')
    META = PrometheusMetric(Info, 'service', 'Meta data about this instance.')

    @classmethod
    def reset(cls):
        metrics = ['TOTAL_TASK_COUNT', 'ACTIVE_TASK_COUNT', 'PROC_RSS_MEM_BYTES',
                   'PROC_RSS_MEM_PERC', 'PROC_CPU_PERC', 'REQUEST_COUNT', 'META']

        for name in metrics:
            metric = getattr(cls, name)
            try:
                cls.registry.unregister(metric)
            except KeyError:
                pass
            finally:
                cls.__dict__[name].reset()
