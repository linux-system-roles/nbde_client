#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sergio Correia <scorreia@redhat.com>
# SPDX-License-Identifier: MIT
#
""" This module is used for handling some operations related to clevis. """

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: nbde_client_clevis
short_description: Handle clevis-related operations on LUKS devices
description:
    - "WARNING: Do not use this module directly! It is only for role internal use."
    - "Module manages clevis bindings on encrypted devices to match the state
      specified in input parameters."
options:
    bindings:
        description: |
            a list of dictionaries that describe a binding that should be
            either added or removed from a given device/slot. It supports
            the following keys:
        type: list
        elements: dict
        suboptions:
            device:
                description:
                    - the path of the underlying encrypted device. This
                      device must be already configured as a LUKS device before
                      using the module (REQUIRED)
            encryption_password:
                description:
                    - a valid password or passphrase for
                      opening/unlocking the specified device
            encryption_key:
                description:
                    - a key file on the managed node valid for
                      opening/unlocking the specified device. When present,
                      the key file should be located at data_dir
            encryption_key_src:
                description:
                    - a key file on the control node valid for
                      opening/unlocking the specified device.  This was copied to
                      data_dir.  This will be used if encryption_key is not specified.
            state:
                description:
                    - either present/absent, to indicate whether the binding
                      described should be added or removed
            slot:
                description:
                    - the slot to use for the binding
            servers:
                description:
                    - the list of servers to bind to
            threshold:
                description:
                    - the threshold for the the Shamir Secret Sharing
                      (SSS) scheme that is put in place when using more than one
                      server
            password_temporary:
                description:
                    - if yes, the password or passphrase that was
                      provided via the encryption_password or encryption_key file arguments
                      will be used to unlock the encrypted device and then it will be removed
                      from the LUKS device after the binding operation completes, i.e., it
                      will not be valid anymore.
    data_dir:
        description:
            - a directory used to store temporary files like encryption_key files
        required: false
        type: str
author:
    - Sergio Correia (@sergio-correia)
"""


EXAMPLES = """
---
- name: Set up a clevis binding in /dev/sda1
  nbde_client_bindings:
    - device: /dev/sda1
      encryption_password: password
      servers:
        - http://server1.example.com
        - http://server2.example.com

- name: Remove binding from slot 2 in /dev/sda1
  nbde_client_bindings:
    - device: /dev/sda1
      encryption_password: password
      slot: 2
      state: absent
"""

RETURN = """
original_bindings:
    description: The original nbde_client_bindings param that was passed in,
      but with the secrets obscured
    type: list
    returned: always
msg:
    description: The output message the module generates
    type: str
    returned: always
"""


import os.path
import json
import re

try:
    from shlex import quote as cmd_quote
except ImportError:
    from pipes import quote as cmd_quote

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}


# The UUID used in LUKSMeta by clevis.
CLEVIS_UUID = "cb6e8904-81ff-40da-a84a-07ab9ab5715e"


class NbdeClientClevisError(Exception):
    """The exceptions thrown by the module"""


def initialize_device(module, luks_type, device):
    """Initialize LUKSMeta. This is required only for LUKS1 devices.
    Return <error>"""

    if luks_type == "luks1":
        args = ["luksmeta", "test", "-d", device]
        ret, _unused, err = module.run_command(args)
        if ret == 0:
            return None

        args = ["luksmeta", "init", "-f", "-d", device]
        ret, _unused, err = module.run_command(args)
        if ret != 0:
            return {"msg": err}

    return None


def get_luks_type(module, device, initialize=True):
    """Get the LUKS type of the device.
    Return: <luks type> <error>"""

    args = ["cryptsetup", "isLuks", device]
    ret_code, _unused, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    # Now let's identify the LUKS type.
    for luks in ["luks1", "luks2"]:
        args = ["cryptsetup", "isLuks", "--type", luks, device]
        ret_code, _unused1, _unused2 = module.run_command(args)
        if ret_code == 0:
            err = None
            if initialize:
                err = initialize_device(module, luks, device)
            return luks, err

    # We did not identify device as either LUKS1 or LUKS2.
    return None, {"msg": "Not possible to detect whether LUKS1 or LUKS2"}


def get_jwe_luks1(module, device, slot):
    """Get a JWE from a specific slot in a LUKS1 device.
    Return: <jwe> <error>"""

    args = ["luksmeta", "show", "-d", device]
    ret_code, stdout, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    # This is the pattern we are looking for:
    # 0   active empty
    # 1   active cb6e8904-81ff-40da-a84a-07ab9ab5715e
    # 2 inactive empty
    pattern = r"^{0}\s+active\s+(\S+)$".format(slot)
    match = re.search(pattern, stdout, re.MULTILINE)
    if not match or (match.groups()[0] != CLEVIS_UUID):
        errmsg = "get_jwe_luks1: {0}:{1} not clevis-bound".format(device, slot)
        return None, {"msg": errmsg}

    args = ["luksmeta", "load", "-d", device, "-s", str(slot)]
    ret_code, stdout, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    return stdout.rstrip(), None


def get_jwe_from_luks2_token(module, token):
    """Retrieve the JWE from a JSON LUKS2 token.
    Return <jwe> <error>"""

    args = ["jose", "fmt", "--json", token, "--object", "--get", "jwe", "--output=-"]
    ret, jwe_obj, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": "get_jwe_from_luks2_token: {0}".format(err)}
    jwe, err = format_jwe(module, jwe_obj, True)
    if err:
        return None, {"msg": "get_jwe_from_luks2_token: {0}".format(err["msg"])}
    return jwe, None


def get_jwe_luks2(module, device, slot):
    """Get a JWE from a specific slot in a LUKS2 device.
    Return: <jwe> <token id> <error>"""

    args = ["cryptsetup", "luksDump", device]
    ret_code, stdout, stderr = module.run_command(args)
    if ret_code != 0:
        return None, None, {"msg": "get_jwe_luks2: {0}".format(stderr)}

    # This is the pattern we are looking for:
    # Tokens:
    #  0: clevis
    #        Keyslot:  1
    # Digests:
    pattern = r"^Tokens:$.*^\s+(\d+):\s+clevis$\s+Keyslot:\s+{0}$.*^Digests:$".format(
        slot
    )

    match = re.search(pattern, stdout, re.MULTILINE | re.DOTALL)
    if not match:
        errmsg = "get_jwe_luks2: {0}:{1} not clevis-bound".format(device, slot)
        return None, None, {"msg": errmsg}

    token_id = match.groups()[0]
    args = ["cryptsetup", "token", "export", "--token-id", token_id, device]
    ret, token, err = module.run_command(args)
    if ret != 0:
        return None, None, {"msg": "get_jwe_luks2: {0}".format(err)}

    jwe, err = get_jwe_from_luks2_token(module, token)
    if err:
        return None, None, {"msg": "get_jwe_luks2: {0}".format(err["msg"])}
    return jwe, token_id, None


def get_jwe(module, device, slot, initialize=True):
    """Get a clevis JWE from a given device and slot.
    Return: <jwe> <error>"""

    luks, err = get_luks_type(module, device, initialize)
    if err:
        return None, err

    if luks == "luks1":
        return get_jwe_luks1(module, device, slot)
    jwe, _unused, err = get_jwe_luks2(module, device, slot)
    return jwe, err


def is_slot_bound(module, device, slot):
    """Checks whether a specific slot in a given device is bound to clevis.
    Return: <boolean> <error>"""

    _unused, err = get_jwe(module, device, slot)
    if err:
        return False, err
    return True, None


def download_adv(module, server):
    """Downloads the advertisement from a specific nbde_server.
    Return: <advertsement> <error>"""

    url = server
    # Add http:// prefix, if missing.
    if not url.startswith("http"):
        url = format("http://{0}".format(url))

    # Add the /adv suffix.
    url = format("{0}/adv".format(url))

    response, info = fetch_url(module, url, method="get")
    if info["status"] != 200:
        return (None, {"msg": info["msg"]})

    try:
        adv_json = json.loads(response.read())
    except ValueError as exc:
        return None, {"msg": str(exc)}

    return adv_json, None


def get_thumbprint(module, key):
    """Gets the tumbprint of the key passed as argument.
    Return <thumbprint> <error>"""

    args = ["jose", "jwk", "thp", "--input=-"]
    ret, thp, _unused = module.run_command(args, data=key, binary_data=True)
    if ret != 0:
        return None, {"msg": "Error getting thumbprint of {0}".format(key)}
    return thp, None


def keys_from_adv(module, adv):
    """Gets the keys from a tang advertisement.
    Return <keys>"""

    keys = {}
    # Get keys from advertisement.
    adv_str = json.dumps(adv)

    args = [
        "jose",
        "fmt",
        "--json=-",
        "--object",
        "--get",
        "payload",
        "--string",
        "--b64load",
        "--object",
        "--get",
        "keys",
        "--output=-",
    ]
    ret, adv_keys_str, _unused = module.run_command(
        args, data=adv_str, binary_data=True
    )
    if ret != 0:
        return keys

    adv_keys = json.loads(adv_keys_str)
    for key in adv_keys:
        key_str = json.dumps(key)
        thp, err = get_thumbprint(module, key_str)
        if err:
            continue
        keys[thp] = thp

    return keys


def generate_config(module, servers, threshold):
    """Creates the config to be used when binding a group of devices.
    Return: <pin> <config> <keys> <error>"""

    # No servers, so there is nothing to do here.
    if not servers or len(servers) == 0:
        return None, None, {}, None

    keys = {}
    nbde_servers = []
    for server in servers:
        adv, err = download_adv(module, server)
        if err:
            return None, None, {}, err
        json_cfg = {"url": server, "adv": adv}
        nbde_servers.append(json_cfg)
        # Get keys from advertisement.
        adv_keys = keys_from_adv(module, adv)
        for key in adv_keys:
            keys[key] = key

    # Multiple servers -> sss pin.
    if len(servers) > 1:
        cfg = {"t": threshold, "pins": {"tang": nbde_servers}}
        return "sss", json.dumps(cfg), keys, None

    # Single server -> tang pin.
    cfg = nbde_servers[0]
    return "tang", json.dumps(cfg), keys, None


def parse_keyslots_luks1(luks_dump):
    """Lists the used keyslots in a LUKS1 device. These may or may not be
    bound to clevis.
    Return: <used keyslots> <error>"""

    if not luks_dump:
        return None, {"msg": "Empty dump provided"}

    # This is the pattern we are looking for:
    # Key Slot 0: ENABLED
    pattern = r"^Key Slot\s(\d+): ENABLED$"
    match = re.findall(pattern, luks_dump, re.MULTILINE)
    if not match:
        errmsg = "parse_keyslots_luks1: no used key slots"
        return (None, {"msg": errmsg})

    return match, None


def parse_keyslots_luks2(luks_dump):
    """Lists the used keyslots in a LUKS2 device. These may or may not be
    bound to clevis.
    Return: <used keyslots> <error>"""

    if not luks_dump:
        return None, {"msg": "Empty dump provided"}

    # This is the pattern we are looking for:
    #   0: clevis
    #         Keyslot:  3
    pattern = r"^\s+(\d+): luks2$"
    match = re.findall(pattern, luks_dump, re.MULTILINE | re.DOTALL)
    if not match:
        errmsg = "parse_keyslots_luks2: no used key slots"
        return None, {"msg": errmsg}
    return match, None


def keyslots_in_use(module, device):
    """Lists the used keyslots in a LUKS device. These may or may not be
    bound to clevis.
    Return: <used keyslots> <error>"""

    luks, err = get_luks_type(module, device)
    if err:
        return None, err

    args = ["cryptsetup", "luksDump", device]
    ret_code, luks_dump, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    if luks == "luks1":
        slots, err = parse_keyslots_luks1(luks_dump)
    else:
        slots, err = parse_keyslots_luks2(luks_dump)

    if err:
        return None, err
    return sorted(slots), None


def bound_slots(module, device):
    """Lists the clevis-bound slots in a LUKS device.
    Return: <bound slots> <error>"""

    slots, err = keyslots_in_use(module, device)
    if err:
        return None, err

    # Now let's iterate through these slots and collect the bound ones.
    bound = []
    for slot in slots:
        _unused, err = is_slot_bound(module, device, slot)
        if err:
            continue
        bound.append(slot)
    return bound, None


def decrypt_jwe(module, jwe):
    """Attempt to decrypt JWE.
    Return: <decrypted JWE> <error>"""

    args = ["clevis", "decrypt"]
    ret, decrypted, err = module.run_command(args, data=jwe, binary_data=True)
    if ret != 0:
        return None, {"msg": err}
    return decrypted, None


def run_cryptsetup(module, args, **kwargs):
    """Run cryptsetup command.
    Return: <output> <error>"""

    passphrase = kwargs.get("passphrase", None)
    is_keyfile = kwargs.get("is_keyfile", False)
    data = kwargs.get("data", None)

    # In order to have extra information when there are failures, let's add
    # --debug to the cryptsetup call here.
    args.extend(["--debug"])

    # Let's check if this is a privileged operation.
    if passphrase is None:
        # No passphrase required, just run the command.
        ret, out, err = module.run_command(args, data=data, binary_data=True)
        if ret != 0:
            errmsg = "Command {0} failed: STDOUT: {1} STDERR: {2}".format(
                " ".join(args), out, err
            )
            return None, {"msg": errmsg}
        return out, None

    # This is privileged operation, so we need to provide either a passphrase
    # or a key file.
    if is_keyfile:
        args.extend(["--key-file", passphrase])
        ret, out, err = module.run_command(args, data=data, binary_data=True)
        if ret != 0:
            errmsg = "Command {0} failed: STDOUT: {1} STDERR: {2}".format(
                " ".join(args), out, err
            )
            return None, {"msg": errmsg}
        return out, None

    # Regular passphrase here.
    if data is None:
        data = passphrase
    else:
        data = "{0}\n{1}".format(passphrase, data)

    ret, out, err = module.run_command(args, data=data, binary_data=True)
    if ret != 0:
        errmsg = "Command {0} failed: STDOUT: {1} STDERR: {2}".format(
            " ".join(args), out, err
        )
        return None, {"msg": errmsg}
    return out, None


def valid_passphrase(module, **kwargs):
    """Tests whether the given passphrase is valid for the specified device.
    Return: <boolean> <error>"""

    for req in ["device", "passphrase"]:
        if req not in kwargs or kwargs[req] is None:
            errmsg = "valid_passphrase: {0} is a required parameter".format(req)
            return False, {"msg": errmsg}

    is_keyfile = kwargs.get("is_keyfile", False)
    slot = kwargs.get("slot", None)

    args = ["cryptsetup", "open", "--test-passphrase", kwargs["device"]]
    if slot is not None:
        args.extend(["--key-slot", str(slot)])

    _unused, err = run_cryptsetup(
        module, args, passphrase=kwargs["passphrase"], is_keyfile=is_keyfile
    )
    if err:
        errmsg = "valid_passphrase: We need a valid passphrase for {0}".format(
            kwargs["device"]
        )
        return False, {"msg": errmsg, "err": err}
    return True, None


def retrieve_passphrase(module, device):
    """Attempt to retrieve a valid passphrase from a clevis-bound device.
    Return: <slot> <passphrase> <error>"""

    slots, err = bound_slots(module, device)
    if err:
        return None, None, err

    for slot in slots:
        jwe, err = get_jwe(module, device, slot)
        if err:
            continue

        decrypted, err = decrypt_jwe(module, jwe)
        if err:
            continue

        _unused, err = valid_passphrase(module, device=device, passphrase=decrypted)
        if err:
            continue
        return slot, decrypted, None

    return None, None, {"msg": "No passphrase retrieved"}


def save_slot_luks1(module, **kwargs):
    """Saves a given data to a specific LUKS1 device and slot. The last
    parameter indicated whether we should overwrite existing metadata.
    Return: <saved> <error>"""

    for req in ["device", "slot", "data", "overwrite"]:
        if req not in kwargs:
            return False, {"msg": "{0} is a required parameter".format(req)}

    if len(kwargs["data"]) == 0:
        return False, {"msg": "We need data to save to a slot"}

    bound, _unused = is_slot_bound(module, kwargs["device"], kwargs["slot"])

    backup, err = backup_luks1_device(module, kwargs["device"])
    if err:
        return False, err

    if bound:
        if not kwargs["overwrite"]:
            errmsg = "{0}:{1} is already bound and no overwrite set".format(
                kwargs["device"], kwargs["slot"]
            )
            return False, {"msg": errmsg}
        args = [
            "luksmeta",
            "wipe",
            "-f",
            "-d",
            kwargs["device"],
            "-s",
            str(kwargs["slot"]),
            "-u",
            CLEVIS_UUID,
        ]
        ret_code, _unused, stderr = module.run_command(args, binary_data=True)
        if ret_code != 0:
            return False, {"msg": stderr}

    args = [
        "luksmeta",
        "save",
        "-d",
        kwargs["device"],
        "-s",
        str(kwargs["slot"]),
        "-u",
        CLEVIS_UUID,
    ]
    ret_code, _unused, stderr = module.run_command(
        args, data=kwargs["data"], binary_data=True
    )
    if ret_code != 0:
        if bound:
            restore_luks1_device(module, kwargs["device"], backup)
        return False, {"msg": stderr}

    # Now make sure we can read the data properly.
    new_data, err = get_jwe_luks1(module, kwargs["device"], kwargs["slot"])
    if err or new_data != kwargs["data"]:
        restore_luks1_device(module, kwargs["device"], backup)
        errmsg = "Error adding JWE to {0}:{1} ; no changes performed".format(
            kwargs["device"], kwargs["slot"]
        )
        return False, {"msg": errmsg}

    return True, None


def backup_luks1_device(module, device):
    """Backup LUKSmeta metadata from LUKS1 device, as it can be corrupted when
    saving new metadata.
    Return: <backup> <error>"""

    bound, err = bound_slots(module, device)
    if err:
        return None, err

    backup = {}
    for slot in bound:
        args = ["luksmeta", "load", "-d", device, "-s", str(slot), "-u", CLEVIS_UUID]
        ret_code, data, stderr = module.run_command(args)
        if ret_code != 0:
            return None, {"msg": stderr}
        backup[slot] = data
    return backup, None


def restore_luks1_device(module, device, backup):
    """Restore LUKSmeta metadata from the specified backup.
    Return: <error>"""

    args = ["luksmeta", "init", "-f", "-d", device]
    ret_code, _unused, stderr = module.run_command(args)
    if ret_code != 0:
        return {"msg": stderr}

    for slot in backup:
        _unused, err = save_slot_luks1(
            module, device=device, slot=slot, data=backup[slot], overwrite=True
        )
        if err:
            return err

    return None


def backup_luks2_token(module, device, token_id):
    """Backup LUKS2 token, as we may need to restore the metadata.
    Return: <backup> <error>"""

    args = ["cryptsetup", "token", "export", "--token-id", token_id, device]
    ret, token, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": "Error during token backup: {0}".format(err)}

    try:
        token_json = json.loads(token)
    except ValueError as exc:
        return None, {"msg": str(exc)}
    return token_json, None


def import_luks2_token(module, device, token):
    """Restore LUKS2 token.
    Return: <error>"""

    if not token or len(token) == 0:
        return {"msg": "import_luks2_token: Invalid token"}

    args = ["cryptsetup", "token", "import", device, "--debug"]
    try:
        token_str = json.dumps(token)
    except ValueError as exc:
        return {"msg": str(exc)}

    ret, _unused, err = module.run_command(args, data=token_str, binary_data=True)
    if ret != 0:
        errmsg = "Error importing token: {0}, token: {1}".format(err, token)
        return {"msg": errmsg}
    return None


def make_luks2_token(slot, data):
    """Prepare a JSON LUKS2 token for a given slot.
    Return <token> <error>"""

    try:
        metadata = {"type": "clevis", "keyslots": [str(slot)], "jwe": json.loads(data)}
    except ValueError as exc:
        return False, {"msg": "Error making new token: {0}".format(str(exc))}

    return metadata, None


def format_jwe(module, data, is_compact):
    """Format JWE to be saved in a LUKS2 token.
    Return <jwe> <error>"""

    args = ["jose", "jwe", "fmt", "--input=-"]
    if is_compact:
        args.append("--compact")
    ret, jwe, err = module.run_command(args, data=data, binary_data=True)
    if ret != 0:
        return None, {"msg": err}
    return jwe.rstrip(), None


def save_slot_luks2(module, **kwargs):
    """Saves a given data to a specific LUKS2 device and slot. The last
    parameter indicates whether we should overwrite existing metadata.
    Return: <saved> <error>"""

    for req in ["device", "slot", "data", "overwrite"]:
        if req not in kwargs:
            return False, {"msg": "{0} is a required parameter".format(req)}

    if len(kwargs["data"]) == 0:
        return False, {"msg": "We need data to save to a slot"}

    old_data, token_id, err = get_jwe_luks2(module, kwargs["device"], kwargs["slot"])

    if not err:
        if not kwargs["overwrite"]:
            errmsg = "{0}:{1} is already bound and no overwrite set".format(
                kwargs["device"], kwargs["slot"]
            )
            return False, {"msg": errmsg}

        old_data, err = backup_luks2_token(module, kwargs["device"], token_id)
        if err:
            return False, err

        args = [
            "cryptsetup",
            "token",
            "remove",
            "--token-id",
            token_id,
            kwargs["device"],
        ]
        ret_code, _unused, err = module.run_command(args)
        if ret_code != 0:
            return False, {"msg": "Error removing token: {0}".format(err)}

    jwe, err = format_jwe(module, kwargs["data"], False)
    if err:
        import_luks2_token(module, kwargs["device"], old_data)
        return False, {"msg": "Error preparing JWE: {0}".format(err["msg"])}

    token, err = make_luks2_token(kwargs["slot"], jwe)
    if err:
        return False, err

    err = import_luks2_token(module, kwargs["device"], token)
    if err:
        import_luks2_token(module, kwargs["device"], old_data)
        return False, err

    # Now the test to see if we stored the correct data.
    metadata, token_id, err = get_jwe_luks2(module, kwargs["device"], kwargs["slot"])
    # get_jwe_luks2 returns the compact version of the data, so let's get it as
    # well for comparison, to see if we have the same data.
    jwe, _unused = format_jwe(module, kwargs["data"], True)
    if err or metadata != jwe:
        # For some reason, what we read was not what we expect.
        # Undo the change.
        args = [
            "cryptsetup",
            "token",
            "remove",
            "--token-id",
            token_id,
            kwargs["device"],
        ]
        module.run_command(args)

        import_luks2_token(module, kwargs["device"], old_data)
        errmsg = "Error storing token: {0} / {1}".format(kwargs["data"], metadata)
        return False, {"msg": errmsg}

    return True, None


def save_slot(module, **kwargs):
    """Saves data to a specific LUKS device and slot.
    Return <saved> <error>"""

    for req in ["device", "slot", "data", "overwrite"]:
        if req not in kwargs:
            return False, {"msg": "{0} is a required parameter".format(req)}

    luks, err = get_luks_type(module, kwargs["device"])
    if err:
        return False, err

    if luks == "luks1":
        return save_slot_luks1(module, **kwargs)
    return save_slot_luks2(module, **kwargs)


def is_keyslot_in_use(module, device, slot):
    """Returns a boolean indicating whether a given slot is in use by a LUKS
    device. This does not mean the slot is clevis-bound necessarily.
    Return: <boolean>"""

    slots, err = keyslots_in_use(module, device)
    if err:
        return False
    return str(slot) in slots


def set_passphrase(module, **kwargs):
    """Adds or replace a LUKS passphrase in a give slot.
    Return: <result> <error>"""

    for req in ["device", "slot", "valid_passphrase", "new_passphrase"]:
        if req not in kwargs:
            return False, {"msg": "{0} is a required parameter".format(req)}

    is_keyfile = kwargs.get("is_keyfile", False)

    # Make sure we actually have a valid password for this device.
    _unused, err = valid_passphrase(
        module,
        device=kwargs["device"],
        passphrase=kwargs["valid_passphrase"],
        is_keyfile=is_keyfile,
    )

    if err:
        errmsg = "We need a valid passphrase for {0}".format(kwargs["device"])
        return False, {"msg": errmsg}

    # Now let's identify whether this is an in-place change, i.e., if
    # the valid passphrase we have is for the slot we are replacing.
    _unused, err = valid_passphrase(
        module,
        device=kwargs["device"],
        passphrase=kwargs["valid_passphrase"],
        is_keyfile=is_keyfile,
        slot=kwargs["slot"],
    )

    in_place = err is None
    if in_place:
        args = [
            "cryptsetup",
            "luksChangeKey",
            kwargs["device"],
            "--key-slot",
            str(kwargs["slot"]),
            "--batch-mode",
            "--force-password",
        ]
        _unused, err = run_cryptsetup(
            module,
            args,
            passphrase=kwargs["valid_passphrase"],
            is_keyfile=is_keyfile,
            data=kwargs["new_passphrase"],
        )
        if err:
            return False, err
        return True, None

    # Not in-place. There are two steps involved: 1) kill the current slot if
    # in use, and # 2) add the new key.
    cmds = []
    if is_keyslot_in_use(module, kwargs["device"], kwargs["slot"]):
        cmds.append(
            [
                "cryptsetup",
                "luksKillSlot",
                "--batch-mode",
                kwargs["device"],
                str(kwargs["slot"]),
            ]
        )

    cmds.append(
        [
            "cryptsetup",
            "luksAddKey",
            "--key-slot",
            str(kwargs["slot"]),
            "--batch-mode",
            "--force-password",
            kwargs["device"],
        ]
    )

    for args in cmds:
        _unused, err = run_cryptsetup(
            module,
            args,
            passphrase=kwargs["valid_passphrase"],
            is_keyfile=is_keyfile,
            data=kwargs["new_passphrase"],
        )

        if err:
            return False, err
    return True, None


def unbind_slot_luks1(module, device, slot):
    """Unbind slot in a LUKS1 device. This involves removing both the clevis
    metadata in LUKSMeta as well as its associated keyslot.
    Return <result> <error>"""
    _unused, err = get_jwe_luks1(module, device, slot)
    if err:
        errmsg = "{0}:{1} is not bound to clevis".format(device, slot)
        return False, {"msg": errmsg}

    cmds = []
    cmds.append(["cryptsetup", "luksKillSlot", "--batch-mode", device, str(slot)])
    cmds.append(
        ["luksmeta", "wipe", "-f", "-d", device, "-u", CLEVIS_UUID, "-s", str(slot)]
    )

    for args in cmds:
        ret, _unused, err = module.run_command(args)
        if ret != 0:
            return False, {"msg": err}
    return True, None


def unbind_slot_luks2(module, device, slot):
    """Unbind slot in a LUKS2 device. This involves removing both the clevis
    metadata as well as its associated keyslot.
    Return <result> <error>"""
    _unused, token_id, err = get_jwe_luks2(module, device, slot)
    if err:
        errmsg = "{0}:{1} is not bound to clevis".format(device, slot)
        return False, {"msg": errmsg}

    cmds = []
    cmds.append(["cryptsetup", "luksKillSlot", "--batch-mode", device, str(slot)])
    cmds.append(["cryptsetup", "token", "remove", "--token-id", token_id, device])

    for args in cmds:
        ret, _unused, err = module.run_command(args)
        if ret != 0:
            return False, {"msg": err}
    return True, None


def unbind_slot(module, device, slot):
    """Unbind slot in a LUKS device. This involves removing the clevis
    metadata as well as its associated passphrase.
    Return: <result> <error>"""

    luks, err = get_luks_type(module, device)
    if err:
        return False, err

    if luks == "luks1":
        return unbind_slot_luks1(module, device, slot)
    return unbind_slot_luks2(module, device, slot)


def new_key(module, device):
    """
    wokeignore:rule=master
    Generate a new key with the same entropy as the LUKS master key.
    Return <key> <error>"""

    luks, err = get_luks_type(module, device)
    if err:
        return None, err

    args = ["cryptsetup", "luksDump", device]
    ret_code, luks_dump, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    pattern = r"^MK bits:[ \t]*([0-9]+)$"
    if luks == "luks2":
        pattern = r"^\s+Key:\s+([0-9]+) bits\s*$"

    match = re.search(pattern, luks_dump, re.MULTILINE)
    if not match:
        errmsg = "new_key: Unable to find entropy bits for {0}".format(device)
        return None, {"msg": errmsg}
    bits = match.groups()[0]
    args = ["pwmake", bits]
    ret, key, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": stderr}
    return key.rstrip(), None


def new_pass_jwe(module, device, pin, pin_cfg):
    """Generates a new pass and returns it and it encrypted with the specified
    pin.
    Return: <pass> <jwe> <error>"""

    key, err = new_key(module, device)
    if err:
        return None, None, err
    args = ["clevis", "encrypt", pin, pin_cfg]
    ret, jwe, err = module.run_command(args, data=key, binary_data=True)
    if ret != 0:
        return None, None, {"msg": err}

    # clevis encrypt can be buggy and return 0 even if it actually failed.
    # Let's try to decrypt the jwe to make sure the operation was actually
    # successful.
    decrypted, err = decrypt_jwe(module, jwe)
    if err or decrypted != key:
        return None, None, {"msg": "Error generating new passphrase"}

    return key, jwe, None


def can_bind_slot(module, device, slot, overwrite):
    """Checks whether we can use this slot for binding clevis.
    Return <result> <error>"""

    # Check if valid LUKS device.
    _unused, err = get_luks_type(module, device)
    if err:
        return False, err

    bound, _unused = is_slot_bound(module, device, slot)
    if bound and not overwrite:
        errmsg = "{0}:{1} is already bound and no overwrite set".format(device, slot)
        return False, {"msg": errmsg}

    # Still need to check whether this slot is not already in use.
    slots, err = keyslots_in_use(module, device)
    if err:
        return False, err
    if not bound and slot in slots:
        errmsg = "slot already used, but not bound by clevis. cannot use it"
        return False, {"msg": errmsg}

    return True, None


def discard_passphrase(module, **kwargs):
    """Discard a passphrase from the LUKS device.
    Return <result> <error>"""

    for req in ["device", "passphrase"]:
        if req not in kwargs:
            return False, {"msg": "{0} is a required parameter".format(req)}

    passphrase = kwargs["passphrase"]
    args = ["cryptsetup", "luksRemoveKey", "--batch-mode", kwargs["device"]]
    is_keyfile = kwargs.get("is_keyfile", False)
    if is_keyfile:
        args.append(passphrase)
        passphrase = None
    ret, _unused, err = module.run_command(args, data=passphrase, binary_data=True)
    if ret != 0:
        return False, {"msg": "Error removing passphrase: {0}".format(err)}
    return True, None


def prepare_to_rebind(module, device, slot):
    """Backups metadata from device and also remove it, in preparation for a
    rebind operation.
    Return <backup> <error>"""

    luks_type, err = get_luks_type(module, device)
    if err:
        return None, err

    if luks_type == "luks1":
        backup, err = backup_luks1_device(module, device)
        if err:
            return None, err
        args = [
            "luksmeta",
            "wipe",
            "-f",
            "-d",
            device,
            "-s",
            str(slot),
            "-u",
            CLEVIS_UUID,
        ]
    else:
        _unused, token_id, err = get_jwe_luks2(module, device, slot)
        if err:
            return err
        backup, err = backup_luks2_token(module, device, token_id)
        if err:
            return None, err
        args = ["cryptsetup", "token", "remove", "--token-id", token_id, device]

    ret, _unused, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": err}
    return backup, None


def restore_failed_rebind(module, device, backup):
    """Restore metadata after a failed rebind operation.
    Return <error>"""

    luks_type, err = get_luks_type(module, device)
    if err:
        return None, err

    if luks_type == "luks1":
        return restore_luks1_device(module, device, backup)
    return import_luks2_token(module, device, backup)


def get_valid_passphrase(module, **kwargs):
    """Gets valid passphrase from input parameters. It first tries to validate
    the passed passphrase, if any, and then tries to retrieve a passphrase from
    existing bindings, otherwise.
    Return <passphrase> <is_keyfile> (boolean) <error>"""

    passphrase = kwargs.get("passphrase", None)
    is_keyfile = kwargs.get("is_keyfile", False)

    # Now let's check if we have a valid passphrase.
    _unused, err = valid_passphrase(
        module,
        device=kwargs["device"],
        passphrase=passphrase,
        is_keyfile=is_keyfile,
    )

    # We have a valid passphrase, so that's fine.
    if not err:
        return passphrase, is_keyfile, None

    # If we provided a passphrase -- which has shown to to be invalid -- and
    # password_temporary is not set, error out.
    password_temporary = kwargs.get("password_temporary", False)
    if not password_temporary and passphrase is not None:
        return None, False, {"msg": "Invalid passphrase for device"}

    # We either were not provided a passphrase, or it didn't prove to be valid,
    # but password_temporary was set.
    # Let's try to retrieve one from existing bindings, if possible.
    _unused, passphrase, err = retrieve_passphrase(module, kwargs["device"])
    if err:
        return None, False, err

    # We retrieved a passphrase from an existing binding, so let's use it.
    is_keyfile = False
    return passphrase, is_keyfile, None


def bind_slot(module, **kwargs):
    """Create a clevis binding in a given LUKS device.
    Return <result> <error>"""

    for req in ["device", "slot", "auth", "auth_cfg"]:
        if req not in kwargs:
            return False, {"msg": "{0} is a required parameter".format(req)}

    overwrite = kwargs.get("overwrite", True)

    _unused, err = can_bind_slot(module, kwargs["device"], kwargs["slot"], overwrite)
    if err:
        return False, err

    passphrase, is_keyfile, err = get_valid_passphrase(module, **kwargs)
    if err:
        return False, err

    discard_pw = kwargs.get("password_temporary", False)
    if discard_pw:
        # Since we have password_temporary set, let's make sure the valid
        # passphrase we have is the one that was given as a parameter. If that
        # is not the case, we cannot consider passphrase to be temporary, which
        # means discard_pw should be false.
        discard_pw = passphrase == kwargs.get("passphrase", None)

    # At this point we can proceed to bind.
    key, jwe, err = new_pass_jwe(
        module, kwargs["device"], kwargs["auth"], kwargs["auth_cfg"]
    )
    if err:
        return False, err

    bound, _unused = is_slot_bound(module, kwargs["device"], kwargs["slot"])

    if bound:
        backup, err = prepare_to_rebind(module, kwargs["device"], kwargs["slot"])
        if err:
            return False, err

    # We add the key first because it will be referenced by the metadata.
    _unused, err = set_passphrase(
        module,
        device=kwargs["device"],
        slot=kwargs["slot"],
        valid_passphrase=passphrase,
        new_passphrase=key,
        is_keyfile=is_keyfile,
    )

    if err:
        if bound:
            restore_failed_rebind(module, kwargs["device"], backup)
        return False, err

    _unused, err = save_slot(
        module, device=kwargs["device"], slot=kwargs["slot"], data=jwe, overwrite=True
    )

    if err:
        return False, err

    # Check if we should discard the valid passphrase we used
    if discard_pw:
        return discard_passphrase(
            module,
            device=kwargs["device"],
            passphrase=passphrase,
            is_keyfile=is_keyfile,
        )

    return True, None


def decode_jwe(module, jwe):
    """Decodes a JWE into its JSON form.
    Return <JSON policy> <error>"""

    args = ["jose", "jwe", "fmt", "--input=-"]
    ret, coded, _unused = module.run_command(args, data=jwe, binary_data=True)
    if ret != 0:
        return None, {"msg": "Error applying jose jwe fmt to given JWE"}

    args = ["jose", "fmt", "--json=-", "--get", "protected", "--unquote=-"]
    ret, coded, _unused = module.run_command(args, data=coded, binary_data=True)
    if ret != 0:
        return None, {"msg": "Error applying jose fmt: {0}".format(coded)}

    args = ["jose", "b64", "dec", "-i-"]
    ret, decoded, _unused = module.run_command(args, data=coded, binary_data=True)
    if ret != 0:
        return None, {"msg": "Error applying jose b64 dec"}

    try:
        jwe_json = json.loads(decoded)
    except ValueError as exc:
        return None, {"msg": str(exc)}
    return jwe_json, None


def decode_pin_tang(module, json_jwe, keys):
    """Decode a tang pin JWE.
    Return <tang (pin)> <tang config> <keys> <error>"""

    if "url" not in json_jwe:
        return None, None, {}, {"msg": "Invalid tang config: no url"}

    if "adv" not in json_jwe or "keys" not in json_jwe["adv"]:
        return None, None, {}, {"msg": "Invalid tang config: no keys in adv"}

    # Let's get the thumbprint of keys.
    for key in json_jwe["adv"]["keys"]:
        key_str = json.dumps(key)
        thp, err = get_thumbprint(module, key_str)
        if err:
            continue
        keys[thp] = thp

    return "tang", {"url": json_jwe["url"]}, keys, None


def decode_pin_tpm2(_module, json_jwe, keys):
    """Decode a tpm2 pin JWE.
    Return <tpm2 (pin)> <tpm2 config> <keys> <error>"""

    pin = {}
    tpm2_keys = ["hash", "key", "pcr_bank", "pcr_ids", "pcr_digest"]
    for key in tpm2_keys:
        if key in json_jwe:
            pin[key] = json_jwe[key]

    return "tpm2", pin, keys, None


def process_pin_sss(module, json_jwe, threshold, keys):
    """Process an sss pin.
    Return <sss (pin)> <sss config> <keys> <error>"""

    pin_cfg = {}
    for coded in json_jwe["jwe"]:
        pin, cfg, pin_keys, err = decode_pin_config(module, coded)
        if err:
            continue

        for key in pin_keys:
            keys[key] = pin_keys[key]

        if pin == "sss":
            pin_cfg[pin] = cfg
        else:
            if pin not in pin_cfg:
                pin_cfg[pin] = []
            pin_cfg[pin].append(cfg)

    cfg = {"t": threshold, "pins": pin_cfg}
    return "sss", cfg, keys, None


def decode_pin_sss(module, json_jwe, keys):
    """Decode an sss pin JWE.
    Return <sss (pin)> <sss config> <keys> <error>"""

    if "t" not in json_jwe:
        return None, None, {}, {"msg": "Invalid sss config: no threshold"}

    threshold = json_jwe["t"]
    return process_pin_sss(module, json_jwe, threshold, keys)


def decode_pin_config(module, jwe):
    """Retrieves the configuration used for the binding represented by the
    JWE passed as argument.
    Return <pin> <policy> <keys> <error>"""

    jwe_json, err = decode_jwe(module, jwe)
    if err:
        return None, None, {}, err

    if "clevis" not in jwe_json or "pin" not in jwe_json["clevis"]:
        return None, None, {}, {"msg": "Invalid clevis pin config"}

    pin = jwe_json["clevis"]["pin"]
    if pin not in jwe_json["clevis"]:
        return None, None, {}, {"msg": "Invalid clevis pin config"}
    config = jwe_json["clevis"][pin]

    decode_method = {
        "tang": decode_pin_tang,
        "tpm2": decode_pin_tpm2,
        "sss": decode_pin_sss,
    }
    if pin not in decode_method:
        return None, None, {}, {"msg": "Unsupported pin '{0}'".format(pin)}

    keys = {}
    return decode_method[pin](module, config, keys)


def already_bound(module, **kwargs):
    """Checks whether there is already a valid/working binding with the same
    configuration as the one we would otherwise add.
    Return <result>"""

    device = kwargs["device"]
    slot = kwargs["slot"]

    # Check #1 - verify whether we have clevis JWE in the slot.
    jwe, err = get_jwe(module, device, slot, False)
    if err:
        return False

    # Check #2 - verify whether the binding works.
    decrypted, err = decrypt_jwe(module, jwe)
    if err:
        return False

    # Check #3 - verify whether the decrypted passphrase is valid.
    _unused, err = valid_passphrase(
        module, device=device, passphrase=decrypted, slot=slot
    )
    if err:
        return False

    # Check #4 - binding is OK, so verify whether configuration is the same.
    original_policy = json.loads(kwargs["auth_cfg"])
    # To simplify the comparison, let's remove the adv key.
    if kwargs["auth"] == "tang":
        original_policy.pop("adv", None)
    else:
        for idx, _unused in enumerate(original_policy["pins"]["tang"]):
            original_policy["pins"]["tang"][idx].pop("adv", None)

    pin, policy, keys, err = decode_pin_config(module, jwe)
    if err or (pin != kwargs["auth"]) or (policy != original_policy):
        return False

    # Check #5 - binding works and has the same configuration.
    # Verify whether there are rotated keys, in which case we should rebind.
    for key in keys:
        if key not in kwargs["keys"]:
            # Key not in advertisements; probably was rotated.
            return False

    return True


def bindings_confidence_check(bindings, data_dir, check_mode):
    """Performs confidence-checking on the bindings list and related arguments.
    Return: <bindings> <error>"""

    # bindings is a list of the following:
    # {
    #   device: [REQUIRED]
    #   encryption_password: a password
    #   encryption_key: /data_dir/filename
    #   encryption_key_src: /path/to/file/on/controlnode
    #   slot: 1 (default)
    #   state: present (default) | absent
    #   password_temporary: no (default)
    #   threshold: 1 (default)
    #   servers: [] (default)
    # }
    if not bindings:
        return None, {"msg": "No devices set"}

    for idx, binding in enumerate(bindings):
        # Set up the state.
        if "state" not in binding:
            bindings[idx]["state"] = "present"
        else:
            if binding["state"] not in ["present", "absent"]:
                errmsg = "state must be present or absent"
                return None, {"msg": errmsg}

        # Make sure we have the required information for the binding.
        if "device" not in binding:
            errmsg = "Each binding must have a device set"
            return None, {"msg": errmsg}

        # When running under check mode, encryption_key is not used, which means we
        # also do not need to have data_dir defined.
        if (
            "encryption_key" in binding or "encryption_key_src" in binding
        ) and not check_mode:
            if not data_dir:
                return None, {"msg": "data_dir needs to be defined"}

            if "encryption_key" in binding:
                basefile = os.path.basename(binding["encryption_key"])
            else:
                basefile = os.path.basename(binding["encryption_key_src"])
            keyfile = os.path.join(data_dir, basefile)
            bindings[idx]["encryption_key"] = cmd_quote(keyfile)

        # The defaults for the remaining binding attributes.
        binding_defaults = {
            "slot": 1,
            "threshold": 1,
            "password_temporary": False,
            "servers": [],
        }

        for attr in binding_defaults:
            if attr not in bindings[idx]:
                bindings[idx][attr] = binding_defaults[attr]

    return bindings, None


def process_bind_operation(module, binding):
    """Process an operation to add a binding to an encrypted device.
    Return: <changed (boolean)> <err>"""

    auth_name, cfg, cfg_keys, err = generate_config(
        module, binding["servers"], binding["threshold"]
    )
    if err:
        raise NbdeClientClevisError(dict(msg=err))

    passphrase = binding.get("encryption_password", None)
    if not passphrase:
        passphrase = binding.get("encryption_key", None)
    is_keyfile = "encryption_key" in binding

    args = dict(
        device=binding["device"],
        slot=binding["slot"],
        auth=auth_name,
        auth_cfg=cfg,
        passphrase=passphrase,
        is_keyfile=is_keyfile,
        overwrite=True,
        keys=cfg_keys,
        password_temporary=binding["password_temporary"],
    )

    if already_bound(module, **args):
        return False, None

    if module.check_mode:
        return True, None

    _unused, err = bind_slot(module, **args)
    if err:
        return False, err

    return True, None


def process_bindings(module, bindings):
    """Process the list of bindings and performs the appropriate operations.
    Return: <result>"""

    original_bindings = bindings
    result = {"changed": False, "original_bindings": bindings}

    for binding in bindings:
        if binding["state"] == "absent":
            _unused, err = is_slot_bound(module, binding["device"], binding["slot"])
            if err:
                # Slot not bound, moving on.
                continue

            if module.check_mode:
                result["changed"] = True
                return result

            _unused, err = unbind_slot(module, binding["device"], binding["slot"])
            if err:
                err["original_bindings"] = original_bindings
                raise NbdeClientClevisError(err)

            result["changed"] = True
        else:
            changed, err = process_bind_operation(module, binding)
            if err:
                err["original_bindings"] = original_bindings
                raise NbdeClientClevisError(err)

            if changed:
                result["changed"] = True
                if module.check_mode:
                    return result

    return result


def obscure_sensitive_parameters(result):
    """Find and obscure sensitive data in nested data structures."""
    if isinstance(result, dict):
        for kk, vv in list(result.items()):
            if kk == "encryption_password":
                result[kk] = "***"
            else:
                obscure_sensitive_parameters(vv)
    elif isinstance(result, list):
        for item in result:
            obscure_sensitive_parameters(item)


def run_module():
    """The entry point of the module."""

    module_args = dict(
        bindings=dict(type="list", elements="dict", required=False),
        data_dir=dict(type="str", required=False),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    params = module.params

    bindings, err = bindings_confidence_check(
        params["bindings"], params["data_dir"], module.check_mode
    )

    if err:
        err["changed"] = False
        result = err
    else:
        try:
            result = process_bindings(module, bindings)
        except NbdeClientClevisError as ncce:
            if len(ncce.args) > 0:
                result = ncce.args[0]
            else:
                result = {"msg": "Module failed"}
            err = result

    result["original_bindings"] = params["bindings"]
    obscure_sensitive_parameters(result)
    if err:
        if "msg" not in result:
            result["msg"] = "Module failed"
        module.fail_json(**result)
    else:
        module.exit_json(**result)


def main():
    """The main function!"""
    run_module()


if __name__ == "__main__":
    main()
