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

# Standard library
import copy
import time
import uuid
from inspect import Signature
from typing import TYPE_CHECKING, Callable, Optional

# Third-party
import uvicorn
from fastapi import FastAPI, APIRouter
from starlette.requests import Request

# Bittensor
import bittensor
from bittensor.core.axon import Axon as axon
from bittensor.core.axon import FastAPIThreadedServer, AxonMiddleware
from bittensor.core.subtensor import Subtensor as subtensor
from bittensor.core.config import Config
from bittensor.core.threadpool import PriorityThreadPoolExecutor
from bittensor.core.extrinsics.serving import do_serve_axon
from bittensor.utils.btlogging import logging
from bittensor.utils import format_error_message, networking as net
from bittensor.utils import ( format_error_message, networking as net, unlock_key, Certificate )
from bittensor.core.types import AxonServeCallParams

# Local
from compute import __version_as_int__
from compute.utils.version import get_local_version

if TYPE_CHECKING:
    from bittensor.core.axon import Axon
    from bittensor.core.subtensor import Subtensor
    from bittensor.core.types import AxonServeCallParams
    from bittensor_wallet import Wallet
    from bittensor.core.subtensor import Subtensor

from bittensor.core.errors import (
    InvalidRequestNameError,
    SynapseParsingError,
    UnknownSynapseError,
)

def custom_serve_extrinsic(
    subtensor: "Subtensor",
    wallet: "Wallet",
    ip: str,
    port: int,
    protocol: int,
    netuid: int,
    placeholder1: int = 0,
    placeholder2: int = 0,
    wait_for_inclusion: bool = False,
    wait_for_finalization: bool =True,
    certificate: Certificate | None = None,
) -> bool:
    """Subscribes a Bittensor endpoint to the subtensor chain.

    Args:
        subtensor (bittensor.core.subtensor.Subtensor): Subtensor instance object.
        wallet (bittensor_wallet.Wallet): Bittensor wallet object.
        ip (str): Endpoint host port i.e., ``192.122.31.4``.
        port (int): Endpoint port number i.e., ``9221``.
        protocol (int): An ``int`` representation of the protocol.
        netuid (int): The network uid to serve on.
        placeholder1 (int): A placeholder for future use.
        placeholder2 (int): A placeholder for future use.
        wait_for_inclusion (bool): If set, waits for the extrinsic to enter a block before returning ``True``, or
            returns ``False`` if the extrinsic fails to enter the block within the timeout.
        wait_for_finalization (bool): If set, waits for the extrinsic to be finalized on the chain before returning
            ``True``, or returns ``False`` if the extrinsic fails to be finalized within the timeout.
        certificate (bittensor.utils.Certificate): Certificate to use for TLS. If ``None``, no TLS will be used.
            Defaults to ``None``.

    Returns:
        success (bool): Flag is ``True`` if extrinsic was finalized or included in the block. If we did not wait for
            finalization / inclusion, the response is ``True``.
    """
    # Decrypt hotkey
    if not (unlock := unlock_key(wallet, "hotkey")).success:
        logging.error(unlock.message)
        return False

    params = AxonServeCallParams(
        version=__version_as_int__,
        ip=net.ip_to_int(ip),
        port=port,
        ip_type=net.ip_version(ip),
        netuid=netuid,
        hotkey=wallet.hotkey.ss58_address,
        coldkey=wallet.coldkeypub.ss58_address,
        protocol=protocol,
        placeholder1=placeholder1,
        placeholder2=placeholder2,
        certificate=certificate,
    )
    logging.debug("Checking axon ...")
    neuron = subtensor.get_neuron_for_pubkey_and_subnet(
        wallet.hotkey.ss58_address, netuid=netuid
    )
    neuron_up_to_date = not neuron.is_null and params == neuron
    if neuron_up_to_date:
        logging.debug(
            f"Axon already served on: AxonInfo({wallet.hotkey.ss58_address},{ip}:{port}) "
        )
        return True

    logging.debug(
        f"Serving axon with: AxonInfo({wallet.hotkey.ss58_address},{ip}:{port}) -> {subtensor.network}:{netuid}"
    )
    success, error_message = do_serve_axon(
        subtensor=subtensor,
        wallet=wallet,
        call_params=params,
        wait_for_finalization=wait_for_finalization,
        wait_for_inclusion=wait_for_inclusion,
    )

    if wait_for_inclusion or wait_for_finalization:
        if success is True:
            logging.debug(
                f"Axon served with: AxonInfo({wallet.hotkey.ss58_address},{ip}:{port}) on {subtensor.network}:{netuid} "
            )
            return True
        else:
            logging.error(f"Failed: {format_error_message(error_message)}")
            return False
    else:
        return True

bittensor.core.extrinsics.serving.serve_extrinsic = custom_serve_extrinsic

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


class ComputeSubnetAxon(axon):
    def __init__(
        self,
        wallet: Optional["Wallet"] = None,
        config: Optional["Config"] = None,
        port: Optional[int] = None,
        ip: Optional[str] = None,
        external_ip: Optional[str] = None,
        external_port: Optional[int] = None,
        max_workers: Optional[int] = None,
    ):
        """Creates a new bittensor.Axon object from passed arguments.

        Args:
            config (:obj:`Optional[bittensor.core.config.Config]`): bittensor.Axon.config()
            wallet (:obj:`Optional[bittensor_wallet.Wallet]`): bittensor wallet with hotkey and coldkeypub.
            port (:type:`Optional[int]`): Binding port.
            ip (:type:`Optional[str]`): Binding ip.
            external_ip (:type:`Optional[str]`): The external ip of the server to broadcast to the network.
            external_port (:type:`Optional[int]`): The external port of the server to broadcast to the network.
            max_workers (:type:`Optional[int]`): Used to create the threadpool if not passed, specifies the number of active threads servicing requests.
        """

        # Build and check config.
        if config is None:
            config = axon.config()
        config = copy.deepcopy(config)
        config.axon.ip = ip or config.axon.ip
        config.axon.port = port or config.axon.port
        config.axon.external_ip = external_ip or config.axon.external_ip
        config.axon.external_port = external_port or config.axon.external_port
        config.axon.max_workers = max_workers or config.axon.max_workers
        axon.check_config(config)
        self.config = config  # type: ignore

        # Get wallet or use default.
        self.wallet = wallet or Wallet(config=self.config)

        # Build axon objects.
        self.uuid = str(uuid.uuid1())
        self.ip = self.config.axon.ip  # type: ignore
        self.port = self.config.axon.port  # type: ignore
        self.external_ip = (
            self.config.axon.external_ip  # type: ignore
            if self.config.axon.external_ip is not None  # type: ignore
            else net.get_external_ip()
        )
        self.external_port = (
            self.config.axon.external_port  # type: ignore
            if self.config.axon.external_port is not None  # type: ignore
            else self.config.axon.port  # type: ignore
        )
        self.full_address = str(self.config.axon.ip) + ":" + str(self.config.axon.port)  # type: ignore
        self.started = False

        # Build middleware
        self.thread_pool = PriorityThreadPoolExecutor(
            max_workers=self.config.axon.max_workers  # type: ignore
        )
        self.nonces: dict[str, int] = {}

        # Request default functions.
        self.forward_class_types: dict[str, list[Signature]] = {}
        self.blacklist_fns: dict[str, Callable | None] = {}
        self.priority_fns: dict[str, Callable | None] = {}
        self.forward_fns: dict[str, Callable | None] = {}
        self.verify_fns: dict[str, Callable | None] = {}


        # Instantiate FastAPI
        self.app = FastAPI()
        log_level = "trace" if logging.__trace_on__ else "critical"
        self.fast_config = uvicorn.Config(
            self.app, host="0.0.0.0", port=self.config.axon.port, log_level=log_level
        )
        self.fast_server = FastAPIThreadedServer(config=self.fast_config)
        self.router = APIRouter()
        self.app.include_router(self.router)

        # Build ourselves as the middleware.
        self.middleware_cls = ComputeSubnetAxonMiddleware
        self.app.add_middleware(self.middleware_cls, axon=self)

        # Attach default forward.
        def ping(r: bittensor.Synapse) -> bittensor.Synapse:
            return r

        self.attach(
            forward_fn=ping, verify_fn=None, blacklist_fn=None, priority_fn=None
        )

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

    async def preprocess(self, request: "Request") -> "Synapse":
        """
        Performs the initial processing of the incoming request. This method is responsible for
        extracting relevant information from the request and setting up the Synapse object, which
        represents the state and context of the request within the Axon server.

        Args:
            request (Request): The incoming request to be preprocessed.

        Returns:
            bittensor.core.synapse.Synapse: The Synapse object representing the preprocessed state of the request.

        The preprocessing involves:

        1. Extracting the request name from the URL path.
        2. Creating a Synapse instance from the request headers using the appropriate class type.
        3. Filling in the Axon and Dendrite information into the Synapse object.
        4. Signing the Synapse from the Axon side using the wallet hotkey.

        This method sets the foundation for the subsequent steps in the request handling process,
        ensuring that all necessary information is encapsulated within the Synapse object.
        """
        # Extracts the request name from the URL path.
        try:
            request_name = request.url.path.split("/")[1]
        except Exception:
            raise InvalidRequestNameError(
                f"Improperly formatted request. Could not parser request {request.url.path}."
            )

        # Creates a synapse instance from the headers using the appropriate forward class type
        # based on the request name obtained from the URL path.
        request_synapse = self.axon.forward_class_types.get(request_name)
        if request_synapse is None:
            raise UnknownSynapseError(
                f"Synapse name '{request_name}' not found. Available synapses {list(self.axon.forward_class_types.keys())}"
            )

        try:
            synapse = request_synapse.from_headers(request.headers)  # type: ignore
        except Exception:
            raise SynapseParsingError(
                f"Improperly formatted request. Could not parse headers {request.headers} into synapse of type {request_name}."
            )
        synapse.name = request_name

        # Fills the local axon information into the synapse.
        synapse.axon.__dict__.update(
            {
                "version": __version_as_int__,
                "uuid": str(self.axon.uuid),
                "nonce": time.monotonic_ns(),
                "status_code": "100"
            }
        )

        # Fills the dendrite information into the synapse.
        synapse.dendrite.__dict__.update(
            {"port": str(request.client.port), "ip": str(request.client.host)}  # type: ignore
        )

        # Signs the synapse from the axon side using the wallet hotkey.
        message = f"{synapse.axon.nonce}.{synapse.dendrite.hotkey}.{synapse.axon.hotkey}.{synapse.axon.uuid}"
        synapse.axon.signature = f"0x{self.axon.wallet.hotkey.sign(message).hex()}"

        # Return the setup synapse.
        return synapse