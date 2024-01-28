import argparse

import bittensor as bt

from compute import miner_hashcat_location, miner_hashcat_workload_profile


class ComputeArgPaser(argparse.ArgumentParser):
    def __init__(self, description=None):
        super().__init__(description=description)
        self.add_argument(
            "--netuid",
            type=int,
            default=27,
            help="The chain subnet uid.",
        )
        self.add_argument(
            "--auto_update",
            action="store_true",
            default=True,
            help="Auto update the git repository.",
        )
        self.add_argument(
            "--blacklist.exploiters",
            dest="blacklist_exploiters",
            default=True,
            action="store_true",
            help="Automatically use the list of internal exploiters hotkeys.",
        )
        self.add_argument(
            "--blacklist.hotkeys",
            type=self.parse_list,
            dest="blacklist_hotkeys",
            help="List of hotkeys to blacklist. Default: [].",
            default=[],
        )
        self.add_argument(
            "--blacklist.coldkeys",
            type=self.parse_list,
            dest="blacklist_coldkeys",
            help="List of coldkeys to blacklist. Default: [].",
            default=[],
        )
        self.add_argument(
            "--whitelist.hotkeys",
            type=self.parse_list,
            dest="whitelist_hotkeys",
            help="List of hotkeys to whitelist. Default: [].",
            default=[],
        )
        self.add_argument(
            "--whitelist.coldkeys",
            type=self.parse_list,
            dest="whitelist_coldkeys",
            help="List of coldkeys to whitelist. Default: [].",
            default=[],
        )

        self.add_validator_argument()
        self.add_miner_argument()

        # Adds subtensor specific arguments i.e. --subtensor.chain_endpoint ... --subtensor.network ...
        bt.subtensor.add_args(self)
        # Adds logging specific arguments i.e. --logging.debug ..., --logging.trace .. or --logging.logging_dir ...
        bt.logging.add_args(self)
        # Adds wallet specific arguments i.e. --wallet.name ..., --wallet.hotkey ./. or --wallet.path ...
        bt.wallet.add_args(self)
        # Adds axon specific arguments i.e. --axon.port ...
        bt.axon.add_args(self)

        self.config = bt.config(self)

    def add_validator_argument(self):
        self.add_argument(
            "--validator.whitelist.unrecognized",
            action="store_true",
            dest="whitelist_unrecognized",
            help="Whitelist the unrecognized miners. Default: False.",
            default=False,
        )
        self.add_argument(
            "--validator.perform.hardware.query",
            action="store_true",
            dest="validator_perform_hardware_query",
            help="Perform the specs method - useful for allocation attempts.",
            default=False,
        )
        self.add_argument(
            "--validator.challenge.batch.size",
            type=int,
            dest="validator_challenge_batch_size",
            help="For lower hardware specifications you might want to use a different batch_size.",
            default=64,
        )
        self.add_argument(
            "--validator.force.update.prometheus",
            action="store_true",
            dest="force_update_prometheus",
            help="Force the try-update of prometheus version. Default: False.",
            default=False,
        )
        self.add_argument(
            "--validator.whitelist.updated.threshold",
            dest="validator_whitelist_updated_threshold",
            help="Total quorum before starting the whitelist. Default: 70.",
            type=int,
            default=70,
        )

    def add_miner_argument(self):
        self.add_argument(
            "--miner.hashcat.path",
            type=str,
            dest="miner_hashcat_path",
            help="The path of the hashcat binary.",
            default=miner_hashcat_location,
        )
        self.add_argument(
            "--miner.hashcat.workload.profile",
            type=str,
            dest="miner_hashcat_workload_profile",
            help="Performance to apply with hashcat profile: 1 Low, 2 Economic, 3 High, 4 Insane. Run `hashcat -h` for more information.",
            default=miner_hashcat_workload_profile,
        )
        self.add_argument(
            "--miner.hashcat.extended.options",
            type=str,
            dest="miner_hashcat_extended_options",
            help="Any extra options you found usefull to append to the hascat runner (I'd perhaps recommend -O). Run `hashcat -h` for more information.",
            default="",
        )
        self.add_argument(
            "--miner.whitelist.not.enough.stake",
            action="store_true",
            dest="miner_whitelist_not_enough_stake",
            help="Whitelist the validators without enough stake. Default: False.",
            default=False,
        )
        self.add_argument(
            "--miner.whitelist.not.updated",
            action="store_true",
            dest="miner_whitelist_not_updated",
            help="Whitelist validators not using the last version of the code. Default: False.",
            default=False,
        )
        self.add_argument(
            "--miner.whitelist.updated.threshold",
            dest="miner_whitelist_updated_threshold",
            help="Total quorum before starting the whitelist. Default: 50.",
            type=int,
            default=50,
        )

    @staticmethod
    def parse_list(arg):
        return arg.split(",")
