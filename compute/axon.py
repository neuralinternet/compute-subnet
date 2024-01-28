# The MIT License (MIT)
# Copyright © 2021 Yuma Rao
# Copyright © 2022 Opentensor Foundation
# Copyright © 2023 Opentensor Technologies Inc
# Copyright © 2023 Rapiiidooo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import copy
import json
import uuid
from typing import Optional

import bittensor
import bittensor.utils.networking as net
import time
import uvicorn
from bittensor import axon, subtensor
from bittensor.axon import FastAPIThreadedServer, AxonMiddleware
from fastapi import FastAPI, APIRouter
from rich.prompt import Confirm
from starlette.requests import Request

from compute import __version_as_int__
from compute.prometheus import prometheus_extrinsic
from compute.utils.version import get_local_version


def serve_extrinsic(
    subtensor: "bittensor.subtensor",
    wallet: "bittensor.wallet",
    ip: str,
    port: int,
    protocol: int,
    netuid: int,
    placeholder1: int = 0,
    placeholder2: int = 0,
    wait_for_inclusion: bool = False,
    wait_for_finalization=True,
    prompt: bool = False,
) -> bool:
    r"""Subscribes a bittensor endpoint to the subtensor chain.
    Args:
        wallet (bittensor.wallet):
            bittensor wallet object.
        ip (str):
            endpoint host port i.e. 192.122.31.4
        port (int):
            endpoint port number i.e. 9221
        protocol (int):
            int representation of the protocol
        netuid (int):
            network uid to serve on.
        placeholder1 (int):
            placeholder for future use.
        placeholder2 (int):
            placeholder for future use.
        wait_for_inclusion (bool):
            if set, waits for the extrinsic to enter a block before returning true,
            or returns false if the extrinsic fails to enter the block within the timeout.
        wait_for_finalization (bool):
            if set, waits for the extrinsic to be finalized on the chain before returning true,
            or returns false if the extrinsic fails to be finalized within the timeout.
        prompt (bool):
            If true, the call waits for confirmation from the user before proceeding.
    Returns:
        success (bool):
            flag is true if extrinsic was finalized or uncluded in the block.
            If we did not wait for finalization / inclusion, the response is true.
    """
    # Decrypt hotkey
    wallet.hotkey
    version = __version_as_int__
    params: "AxonServeCallParams" = {
        "version": version,
        "ip": net.ip_to_int(ip),
        "port": port,
        "ip_type": net.ip_version(ip),
        "netuid": netuid,
        "hotkey": wallet.hotkey.ss58_address,
        "coldkey": wallet.coldkeypub.ss58_address,
        "protocol": protocol,
        "placeholder1": placeholder1,
        "placeholder2": placeholder2,
    }
    bittensor.logging.debug("Checking axon ...")
    neuron = subtensor.get_neuron_for_pubkey_and_subnet(wallet.hotkey.ss58_address, netuid=netuid)
    neuron_up_to_date = not neuron.is_null and params == {
        "version": neuron.axon_info.version,
        "ip": net.ip_to_int(neuron.axon_info.ip),
        "port": neuron.axon_info.port,
        "ip_type": neuron.axon_info.ip_type,
        "netuid": neuron.netuid,
        "hotkey": neuron.hotkey,
        "coldkey": neuron.coldkey,
        "protocol": neuron.axon_info.protocol,
        "placeholder1": neuron.axon_info.placeholder1,
        "placeholder2": neuron.axon_info.placeholder2,
    }
    output = params.copy()
    output["coldkey"] = wallet.coldkeypub.ss58_address
    output["hotkey"] = wallet.hotkey.ss58_address
    if neuron_up_to_date:
        bittensor.logging.debug(f"Axon already served on: AxonInfo({wallet.hotkey.ss58_address},{ip}:{port}) ")
        return True

    if prompt:
        output = params.copy()
        output["coldkey"] = wallet.coldkeypub.ss58_address
        output["hotkey"] = wallet.hotkey.ss58_address
        if not Confirm.ask("Do you want to serve axon:\n  [bold white]{}[/bold white]".format(json.dumps(output, indent=4, sort_keys=True))):
            return False

    bittensor.logging.debug(f"Serving axon with: AxonInfo({wallet.hotkey.ss58_address},{ip}:{port}) -> {subtensor.network}:{netuid}:{version}")
    success, error_message = subtensor._do_serve_axon(
        wallet=wallet,
        call_params=params,
        wait_for_finalization=wait_for_finalization,
        wait_for_inclusion=wait_for_inclusion,
    )

    if wait_for_inclusion or wait_for_finalization:
        if success == True:
            bittensor.logging.debug(f"Axon served with: AxonInfo({wallet.hotkey.ss58_address},{ip}:{port}) on {subtensor.network}:{netuid} ")
            return True
        else:
            bittensor.logging.debug(f"Axon failed to served with error: {error_message} ")
            return False
    else:
        return True


class ComputeSubnetSubtensor(subtensor):
    def __init__(
        self,
        network: str = None,
        config: "bittensor.config" = None,
        _mock: bool = False,
        log_verbose: bool = True,
    ) -> None:
        super().__init__(
            network=network,
            config=config,
            _mock=_mock,
            log_verbose=log_verbose,
        )

    #################
    #### Serving ####
    #################
    def serve(
        self,
        wallet: "bittensor.wallet",
        ip: str,
        port: int,
        protocol: int,
        netuid: int,
        placeholder1: int = __version_as_int__,
        placeholder2: int = 0,
        wait_for_inclusion: bool = False,
        wait_for_finalization=True,
        prompt: bool = False,
    ) -> bool:
        serve_extrinsic(
            self,
            wallet,
            ip,
            port,
            protocol,
            netuid,
            placeholder1,
            placeholder2,
            wait_for_inclusion,
            wait_for_finalization,
        )

    def serve_prometheus(
        self,
        wallet: "bittensor.wallet",
        port: int,
        netuid: int,
        wait_for_inclusion: bool = False,
        wait_for_finalization: bool = True,
        force_update: bool = False,
    ) -> bool:
        return prometheus_extrinsic(
            self,
            wallet=wallet,
            port=port,
            netuid=netuid,
            wait_for_inclusion=wait_for_inclusion,
            wait_for_finalization=wait_for_finalization,
            force_update=force_update,
        )


class ComputeSubnetAxon(axon):
    def __init__(
        self,
        wallet: "bittensor.wallet" = None,
        config: Optional["bittensor.config"] = None,
        port: Optional[int] = None,
        ip: Optional[str] = None,
        external_ip: Optional[str] = None,
        external_port: Optional[int] = None,
        max_workers: Optional[int] = None,
    ) -> "bittensor.axon":
        r"""Creates a new bittensor.Axon object from passed arguments.
        Args:
            config (:obj:`Optional[bittensor.config]`, `optional`):
                bittensor.axon.config()
            wallet (:obj:`Optional[bittensor.wallet]`, `optional`):
                bittensor wallet with hotkey and coldkeypub.
            port (:type:`Optional[int]`, `optional`):
                Binding port.
            ip (:type:`Optional[str]`, `optional`):
                Binding ip.
            external_ip (:type:`Optional[str]`, `optional`):
                The external ip of the server to broadcast to the network.
            external_port (:type:`Optional[int]`, `optional`):
                The external port of the server to broadcast to the network.
            max_workers (:type:`Optional[int]`, `optional`):
                Used to create the threadpool if not passed, specifies the number of active threads servicing requests.
        """
        # Build and check config.
        if config is None:
            config = axon.config()
        config = copy.deepcopy(config)
        config.axon.ip = ip or config.axon.get("ip", bittensor.defaults.axon.ip)
        config.axon.port = port or config.axon.get("port", bittensor.defaults.axon.port)
        config.axon.external_ip = external_ip or config.axon.get("external_ip", bittensor.defaults.axon.external_ip)
        config.axon.external_port = external_port or config.axon.get("external_port", bittensor.defaults.axon.external_port)
        config.axon.max_workers = max_workers or config.axon.get("max_workers", bittensor.defaults.axon.max_workers)
        axon.check_config(config)
        self.config = config

        # Get wallet or use default.
        self.wallet = wallet or bittensor.wallet()

        # Build axon objects.
        self.uuid = str(uuid.uuid1())
        self.ip = self.config.axon.ip
        self.port = self.config.axon.port
        self.external_ip = self.config.axon.external_ip if self.config.axon.external_ip != None else bittensor.utils.networking.get_external_ip()
        self.external_port = self.config.axon.external_port if self.config.axon.external_port != None else self.config.axon.port
        self.full_address = str(self.config.axon.ip) + ":" + str(self.config.axon.port)
        self.started = False

        # Build middleware
        self.thread_pool = bittensor.PriorityThreadPoolExecutor(max_workers=self.config.axon.max_workers)
        self.nonces = {}

        # Request default functions.
        self.forward_class_types = {}
        self.blacklist_fns = {}
        self.priority_fns = {}
        self.forward_fns = {}
        self.verify_fns = {}
        self.required_hash_fields = {}

        # Instantiate FastAPI
        self.app = FastAPI()
        log_level = "trace" if bittensor.logging.__trace_on__ else "critical"
        self.fast_config = uvicorn.Config(self.app, host="0.0.0.0", port=self.config.axon.port, log_level=log_level)
        self.fast_server = FastAPIThreadedServer(config=self.fast_config)
        self.router = APIRouter()
        self.app.include_router(self.router)

        # Build ourselves as the middleware.
        self.app.add_middleware(ComputeSubnetAxonMiddleware, axon=self)

        # Attach default forward.
        def ping(r: bittensor.Synapse) -> bittensor.Synapse:
            return r

        self.attach(forward_fn=ping, verify_fn=None, blacklist_fn=None, priority_fn=None)

    def info(self) -> "bittensor.AxonInfo":
        """Returns the axon info object associated with this axon."""
        return bittensor.AxonInfo(
            version=get_local_version(),
            ip=self.external_ip,
            ip_type=4,
            port=self.external_port,
            hotkey=self.wallet.hotkey.ss58_address,
            coldkey=self.wallet.coldkeypub.ss58_address,
            protocol=4,
            placeholder1=1,
            placeholder2=2,
        )


class ComputeSubnetAxonMiddleware(AxonMiddleware):
    """
    The `AxonMiddleware` class is a key component in the Axon server, responsible for processing all
    incoming requests. It handles the essential tasks of verifying requests, executing blacklist checks,
    running priority functions, and managing the logging of messages and errors. Additionally, the class
    is responsible for updating the headers of the response and executing the requested functions.

    This middleware acts as an intermediary layer in request handling, ensuring that each request is
    processed according to the defined rules and protocols of the Bittensor network. It plays a pivotal
    role in maintaining the integrity and security of the network communication.

    Args:
        app (FastAPI): An instance of the FastAPI application to which this middleware is attached.
        axon (bittensor.axon): The Axon instance that will process the requests.

    The middleware operates by intercepting incoming requests, performing necessary preprocessing
    (like verification and priority assessment), executing the request through the Axon's endpoints, and
    then handling any postprocessing steps such as response header updating and logging.
    """

    def __init__(self, app: "AxonMiddleware", axon: "bittensor.axon"):
        """
        Initialize the AxonMiddleware class.

        Args:
        app (object): An instance of the application where the middleware processor is used.
        axon (object): The axon instance used to process the requests.
        """
        super().__init__(app, axon=axon)

    async def preprocess(self, request: Request) -> bittensor.Synapse:
        """
        Performs the initial processing of the incoming request. This method is responsible for
        extracting relevant information from the request and setting up the Synapse object, which
        represents the state and context of the request within the Axon server.

        Args:
            request (Request): The incoming request to be preprocessed.

        Returns:
            bittensor.Synapse: The Synapse object representing the preprocessed state of the request.

        The preprocessing involves:
        1. Extracting the request name from the URL path.
        2. Creating a Synapse instance from the request headers using the appropriate class type.
        3. Filling in the Axon and Dendrite information into the Synapse object.
        4. Signing the Synapse from the Axon side using the wallet hotkey.

        This method sets the foundation for the subsequent steps in the request handling process,
        ensuring that all necessary information is encapsulated within the Synapse object.
        """
        # Extracts the request name from the URL path.
        request_name = request.url.path.split("/")[1]

        # Creates a synapse instance from the headers using the appropriate forward class type
        # based on the request name obtained from the URL path.
        synapse = self.axon.forward_class_types[request_name].from_headers(request.headers)
        synapse.name = request_name

        # Fills the local axon information into the synapse.
        synapse.axon.__dict__.update(
            {
                "version": __version_as_int__,
                "uuid": str(self.axon.uuid),
                "nonce": f"{time.monotonic_ns()}",
                "status_message": "Success",
                "status_code": "100",
                "placeholder1": 1,
                "placeholder2": 2,
            }
        )

        # Fills the dendrite information into the synapse.
        synapse.dendrite.__dict__.update({"port": str(request.client.port), "ip": str(request.client.host)})

        # Signs the synapse from the axon side using the wallet hotkey.
        message = f"{synapse.axon.nonce}.{synapse.dendrite.hotkey}.{synapse.axon.hotkey}.{synapse.axon.uuid}"
        synapse.axon.signature = f"0x{self.axon.wallet.hotkey.sign(message).hex()}"

        # Return the setup synapse.
        return synapse
