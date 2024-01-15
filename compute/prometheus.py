# The MIT License (MIT)
# Copyright © 2021 Yuma Rao
# Copyright © 2023 Opentensor Foundation
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

import bittensor
import bittensor.utils.networking as net

import compute


def prometheus_extrinsic(
    subtensor: "bittensor.subtensor",
    wallet: "bittensor.wallet",
    port: int,
    netuid: int,
    ip: int = None,
    wait_for_inclusion: bool = False,
    wait_for_finalization=True,
    force_update: bool = False,
) -> bool:
    r"""Subscribes a bittensor endpoint to the subtensor chain.
    Args:
        subtensor (bittensor.subtensor):
            bittensor subtensor object.
        wallet (bittensor.wallet):
            bittensor wallet object.
        ip (str):
            endpoint host port i.e. 192.122.31.4
        port (int):
            endpoint port number i.e. 9221
        netuid (int):
            network uid to serve on.
        wait_for_inclusion (bool):
            if set, waits for the extrinsic to enter a block before returning true,
            or returns false if the extrinsic fails to enter the block within the timeout.
        wait_for_finalization (bool):
            if set, waits for the extrinsic to be finalized on the chain before returning true,
            or returns false if the extrinsic fails to be finalized within the timeout.
        force_update (bool):
            If set, force the try-update of prometheus version.
    Returns:
        success (bool):
            flag is true if extrinsic was finalized or included in the block.
            If we did not wait for finalization / inclusion, the response is true.
    """

    # ---- Get external ip ----
    if ip == None:
        try:
            external_ip = net.get_external_ip()
            bittensor.logging.trace("Found external ip: {}".format(external_ip))
        except Exception as E:
            raise RuntimeError("Unable to attain your external ip. Check your internet connection. error: {}".format(E)) from E
    else:
        external_ip = ip

    call_params: "PrometheusServeCallParams" = {
        "version": compute.__version_as_int__,
        "ip": net.ip_to_int(external_ip),
        "port": port,
        "ip_type": net.ip_version(external_ip),
    }

    bittensor.logging.info("Checking Prometheus...")
    neuron = subtensor.get_neuron_for_pubkey_and_subnet(wallet.hotkey.ss58_address, netuid=netuid)

    curr_block = subtensor.block - (subtensor.block % 100)
    last_update = curr_block - neuron.last_update
    if last_update > 100 or force_update:
        bittensor.logging.info("Needs to re-update neuron...")
        neuron_up_to_date = None
    else:
        bittensor.logging.info("Neuron has been updated less than 100 blocks ago...")
        neuron_up_to_date = not neuron.is_null and call_params == {
            "version": compute.__version_as_int__,
            "ip": net.ip_to_int(neuron.prometheus_info.ip),
            "port": neuron.prometheus_info.port,
            "ip_type": neuron.prometheus_info.ip_type,
        }

    if neuron_up_to_date:
        bittensor.logging.info(f"Prometheus already Served.")
        return True

    # Add netuid, not in prometheus_info
    call_params["netuid"] = netuid

    bittensor.logging.info("Serving prometheus on: {}:{} ...".format(subtensor.network, netuid))
    success, err = subtensor._do_serve_prometheus(
        wallet=wallet,
        call_params=call_params,
        wait_for_finalization=wait_for_finalization,
        wait_for_inclusion=wait_for_inclusion,
    )

    if wait_for_inclusion or wait_for_finalization:
        if success == True:
            return True
        else:
            bittensor.logging.error("Failed to serve prometheus error: {}".format(err))
            return False
    else:
        return True
