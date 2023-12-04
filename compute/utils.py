import compute
import bittensor as bt
import time
from datetime import datetime
import codecs
import re
import os

update_flag = False
update_at = 0

def timestamp_to_datestring(timestamp):
    # Convert the timestamp to a datetime object
    dt_object = datetime.fromtimestamp(timestamp)

    # Format the datetime object as an ISO 8601 string
    iso_date_string = dt_object.isoformat()
    return iso_date_string

def set_update_flag():
    global update_flag
    global update_at
    if update_flag:
        bt.logging.info(f"🧭 Auto Update scheduled on {timestamp_to_datestring(update_at)}")
        return
    update_flag = True
    update_at = time.time() + 120
    bt.logging.info(f"🧭 Auto Update scheduled on {timestamp_to_datestring(update_at)}")

"""
Checks if the provided version matches the current compute protocol version.

Args:
    version (compute.protocol.Version): The version to check.
    flag: major | minor | patch | no

Returns:
    bool: True if the versions match, False otherwise.
"""
def check_version( version: compute.protocol.Version, flag ) -> bool:
    global update_flag
    version_str = compute.__version__
    major, minor, patch = version_str.split('.')
    other_version_str = f"{version.major_version}.{version.minor_version}.{version.patch_version}"
    if version.major_version != int(major):
        bt.logging.error("🔴 Major version mismatch", f"yours: {version_str}, other's: {other_version_str}")
        if version.major_version > int(major) and flag != 'no':
            set_update_flag()
        return False
    elif version.minor_version != int(minor):
        bt.logging.warning("🟡 Minor version mismatch", f"yours: {version_str}, other's: {other_version_str}")
        if version.minor_version > int(minor) and (flag == 'minor' or flag == 'patch'):
            set_update_flag()
    elif version.patch_version != int(patch):
        bt.logging.warning("🔵 Patch version mismatch", f"yours: {version_str}, other's: {other_version_str}")
        if version.patch_version > int(patch) and flag == 'patch':
            set_update_flag()
    return True


"""
Retrieves the current version of the compute protocol being used.

Returns:
    compute.protocol.Version: The version object with major, minor, and patch components.
"""
def get_my_version() -> compute.protocol.Version:
    version_str = compute.__version__
    major, minor, patch = version_str.split('.')
    return compute.protocol.Version(
        major_version = int(major),
        minor_version = int(minor),
        patch_version = int(patch)
    )

'''
Update repository if there is a new version available
'''
def update_repository(flag = 'patch'):
    bt.logging.info("Updating repository")
    os.system("git pull")
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, '__init__.py'), encoding='utf-8') as init_file:
        version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", init_file.read(), re.M)
        new_version = version_match.group(1)
        bt.logging.success(f"current version: {compute.__version__}, new version: {new_version}")
        new_major, new_minor, new_patch = new_version.split('.')
        major, minor, patch = compute.__version__.split('.')
        if new_version != compute.__version__:
            os.system("python -e pip install -e .")
        if major != new_major:
            return True
        if flag == 'major':
            return False
        if minor != new_minor:
            return True
        if flag == 'minor':
            return False
        if patch != new_patch:
            return True
    return False

def check_for_update(flag = 'patch'):
    global update_flag
    global update_at
    while True:
        if update_flag:
            if time.time() >= update_at:
                update_repository(flag)
                bt.logging.info("🔁 Exiting process for update.")
                os._exit(0)
            return
        time.sleep(1)