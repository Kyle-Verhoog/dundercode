from datadog import DDClient, DDConfig

ddcfg = DDConfig(
    service="dundercode",
    tracing_enabled=True,
    version_use_git=True,
    agent_run=False,
)
ddclient = DDClient(config=ddcfg)
