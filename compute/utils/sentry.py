from bittensor import config as Config
import bittensor as bt

from compute import __version__

def init_sentry(config : Config, tags : dict = {}):
    if config.sentry_dsn is None:
        bt.logging.info(f"Sentry is DISABLED")
        return

    bt.logging.info(f"Sentry is ENABLED. Using dsn={config.sentry_dsn}")
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        release=__version__,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0
    )

    sentry_sdk.set_tag("netuid", config.netuid)

    for key, value in tags.items():
        sentry_sdk.set_tag(key, value)