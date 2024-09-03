import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
import requests
import bittensor as bt
import os
from dotenv import load_dotenv

MAX_NOTIFY_RETRY = 3
NOTIFY_RETRY_PERIOD = 10 

load_dotenv()
deallocation_notify_url = os.getenv("DEALLOCATION_NOTIFY_URL")
status_notify_url = os.getenv("STATUS_NOTIFY_URL")


async def notify_allocation_status( event_time: datetime, hotkey: str,
                                        uuid: str, event: str, details: str | None = ""):
        """
        Notify the allocation by hotkey and status. <br>
        """
        headers = {
            'accept': '*/*',
            'Content-Type': 'application/json',
        }
        
        msg = {
            "time" : datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "hotkey": hotkey,
            "status": event,
            "uuid": uuid,
        }
        if event == "DEALLOCATION":
            msg['deallocated_at'] = event_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            notify_url = deallocation_notify_url
        elif event == "OFFLINE" or event == "ONLINE":
            msg['status_change_at'] = event_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            notify_url = status_notify_url

        retries = 0
        while retries < MAX_NOTIFY_RETRY or event == "DEALLOCATION":
            try:
                # Send the POST request
                data = json.dumps(msg)
                response = requests.post(notify_url, headers=headers, data=data, timeout=3, json=True, verify=False,
                                         cert=("cert/server.cer", "cert/server.key"))
                # Check for the expected ACK in the response
                if response.status_code == 200 or response.status_code == 201:
                    response_data = response.json()
                    bt.logging.info(f"API: Notify {hotkey} succeeded with {response.status_code} status code: ")
                    return response_data
                else:
                    bt.logging.info(f"API: Notify failed with {hotkey} status code: "
                                    f"{response.status_code}, response: {response.text}")
                    # return None
            except requests.exceptions.RequestException as e:
                bt.logging.info(f"API: Notify {hotkey} failed: {e}")

            # Increment the retry counter and wait before retrying
            retries += 1
            await asyncio.sleep(NOTIFY_RETRY_PERIOD)
        return None