import bittensor
import wandb

from neurons.Validator.script import get_perf_info

PUBLIC_WANDB_NAME = "opencompute"
PUBLIC_WANDB_ENTITY = "neuralinternet"


class ComputeWandb:
    run = None

    def __init__(self, config: bittensor.config, hotkey, role: str):
        self.config = config.copy()
        del self.config["logging"]["logging_dir"]
        del self.config["wallet"]
        del self.config["full_path"]
        del self.config["axon"]

        self.hotkey = hotkey
        self.role = role
        self.entity = PUBLIC_WANDB_ENTITY

        self.api = wandb.Api()
        self.project = self.api.project(PUBLIC_WANDB_NAME)
        self.project_run_id = f"{self.entity}/{self.project.name}"

        try:
            self.run = wandb.init(project=self.project.name, entity=self.entity)
        except Exception as e:
            bittensor.logging.warning(f"wandb init failed: {e}")

        self.update_config()

    def update_config(self):
        if self.run:
            self.run.config["hotkey"] = self.hotkey
            self.run.config["role"] = self.role
            self.run.config["config"] = self.config
        else:
            bittensor.logging.warning(f"wandb init failed, update config not possible.")

    def update_specs(self):
        """
        You can fake these information. Do it at your own risk.
        The validators will send the number of challenges accordingly to the specifications provided here.
        So if you fake something you'll end with a very degraded score :clown:.
        Also, when your miner is allocated, the allocated user can give back a mark of reliability.
        The smaller reliability is, the faster you'll be dereg.
        """
        if self.run:
            self.run.config["specs"] = get_perf_info(encrypted=False)
        else:
            bittensor.logging.warning(f"wandb init failed, update specs not possible.")

    def update_allocated(self, allocated):
        """
        This function update the allocated value on miner side.
        It's useless to fake this information because its only used as public purpose.
        Not used by the validators to calculate your steak :meat:.
        """
        if self.run:
            self.run.config["allocated"] = allocated
        else:
            bittensor.logging.warning(f"wandb init failed, update allocated not possible.")

    def update_stats(self, stats: dict):
        if self.run:
            self.run.config["stats"] = stats
        else:
            bittensor.logging.warning(f"wandb init failed, update stats not possible.")

    # def update_allocation(self, hotkey: str, allocated: bool):
    #     artifact = wandb.Artifact("allocated", type="dataset")
    #     artifact.add({hotkey: allocated}, hotkey)
    #     self.run.log_artifact(artifact)

    # @staticmethod
    # def update_db():
    #     artifact = wandb.Artifact("db", type="dataset")
    #     artifact.add_file("database.db")
    #     artifact.description = "Validator database."
    #
    #     run_db = wandb.init(project=PUBLIC_WANDB_NAME, job_type="database-upload")
    #     run_db.log_artifact(artifact)
