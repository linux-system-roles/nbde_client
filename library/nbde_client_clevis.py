#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sergio Correia <scorreia@redhat.com>
# SPDX-License-Identifier: MIT
#
""" This module is used for handling some operations related to clevis. """

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


DOCUMENTATION = """
---
module: nbde_client_clevis
short_description: Handle clevis-related operations on LUKS devices
version_added: "2.5"
description:
    - "Module manages clevis bindings on LUKS devices to match the state
       specified in input parameters.
options:
    devices:
        description:
            - list of dicts containing a set of LUKS devices and a specific
              binding configuration to be applied to this set of devices.
        required: true
author:
    - Sergio Correia (scorreia@redhat.com)
"""


EXAMPLES = """
---
- name: Set up a clevis binding in /dev/sda1
  nbde_client_bindings:
    - devices:
        - path: /dev/sda1
          pass: password
      auth:
        servers:
          - http://tang.server-01
          - http://tang.server-02


- name: Remove binding from slot 2 in /dev/sda1
  nbde_client_bindings:
    - devices:
        - path: /dev/sda1
          pass: password
      state: absent
      auth:
        slot: 2
"""

RETURN = """
original_bindings::
    description: The original nbde_client_bindings param that was passed in
    type: list
    returned: always
msg:
    description: The output message the module generates
    type: str
    returned: always
"""


# The UUID used in LUKSMeta by clevis.
CLEVIS_UUID = "cb6e8904-81ff-40da-a84a-07ab9ab5715e"


class NbdeClientClevisError(Exception):
    """ The exceptions thrown by the module  """


def initialize_device(module, luks_type, device):
    """ Initialize LUKSMeta. This is required only for LUKS1 devices.
    Return <error> """

    if luks_type == "luks1":
        args = ["luksmeta", "test", "-d", device]
        ret, _, err = module.run_command(args)
        if ret == 0:
            return None

        args = ["luksmeta", "init", "-f", "-d", device]
        ret, _, err = module.run_command(args)
        if ret != 0:
            return {"msg": err}

    return None


def get_luks_type(module, device):
    """ Get the LUKS type of the device.
    Return: <luks type> <error> """

    args = ["cryptsetup", "isLuks", device]
    ret_code, _, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    # Now let's identify the LUKS type.t
    for luks in ["luks1", "luks2"]:
        args = ["cryptsetup", "isLuks", "--type", luks, device]
        ret_code, _, _ = module.run_command(args)
        if ret_code == 0:
            err = initialize_device(module, luks, device)
            return luks, err

    # We did not identify device as either LUKS1 or LUKS2.
    return None, {"msg": "Not possible to detect whether LUKS1 or LUKS2"}


def get_jwe_luks1(module, device, slot):
    """ Get a JWE from a specific slot in a LUKS1 device.
    Return: <jwe> <error> """

    args = ["luksmeta", "show", "-d", device]
    ret_code, stdout, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    # This is the pattern we are looking for:
    # 0   active empty
    # 1   active cb6e8904-81ff-40da-a84a-07ab9ab5715e
    # 2 inactive empty
    pattern = r"^{}\s+active\s+(\S+)$".format(slot)
    match = re.search(pattern, stdout, re.MULTILINE)
    if not match or (match.groups()[0] != CLEVIS_UUID):
        errmsg = "get_jwe_luks1: {}:{} not clevis-bound".format(device, slot)
        return None, {"msg": errmsg}

    args = ["luksmeta", "load", "-d", device, "-s", str(slot)]
    ret_code, stdout, stderr = module.run_command(args)
    if ret_code != 0:
        return None, {"msg": stderr}

    return stdout.rstrip(), None


def get_jwe_from_luks2_token(module, token):
    """ Retrieve the JWE from a JSON LUKS2 token.
    Return <jwe> <error> """

    args = ["jose", "fmt", "--json", token, "--object", "--get", "jwe", "--output=-"]
    ret, jwe_obj, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": "get_jwe_from_luks2_token: {}".format(err)}
    jwe, err = format_jwe(module, jwe_obj, True)
    if err:
        return None, {"msg": "get_jwe_from_luks2_token: {}".format(err["msg"])}
    return jwe, None


def get_jwe_luks2(module, device, slot):
    """ Get a JWE from a specific slot in a LUKS2 device.
    Return: <jwe> <token id> <error> """

    args = ["cryptsetup", "luksDump", device]
    ret_code, stdout, stderr = module.run_command(args)
    if ret_code != 0:
        return None, None, {"msg": "get_jwe_luks2: {}".format(stderr)}

    # This is the pattern we are looking for:
    # Tokens:
    #  0: clevis
    #        Keyslot:  1
    # Digests:
    pattern = r"^Tokens:$.*^\s+(\d+):\s+clevis$\s+Keyslot:\s+{}$.*^Digests:$".format(
        slot
    )

    match = re.search(pattern, stdout, re.MULTILINE | re.DOTALL)
    if not match:
        errmsg = "get_jwe_luks2: {}:{} not clevis-bound".format(device, slot)
        return None, None, {"msg": errmsg}

    token_id = match.groups()[0]
    args = ["cryptsetup", "token", "export", "--token-id", token_id, device]
    ret, token, err = module.run_command(args)
    if ret != 0:
        return None, None, {"msg": "get_jwe_luks2: {}".format(err)}

    jwe, err = get_jwe_from_luks2_token(module, token)
    if err:
        return None, None, {"msg": "get_jwe_luks2: {}".format(err["msg"])}
    return jwe, token_id, None


def get_jwe(module, device, slot):
    """ Get a clevis JWE from a given device and slot.
    Return: <jwe> <error> """

    luks, err = get_luks_type(module, device)
    if err:
        return None, err

    if luks == "luks1":
        return get_jwe_luks1(module, device, slot)
    jwe, _, err = get_jwe_luks2(module, device, slot)
    return jwe, err


def is_slot_bound(module, device, slot):
    """ Checks whether a specific slot in a given device is bound to clevis.
    Return: <boolean> <error> """

    _, err = get_jwe(module, device, slot)
    if err:
        return False, err
    return True, None


def download_adv(module, server):
    """ Downloads the advertisement from a specific nbde_server.
    Return: <advertsement> <error> """

    url = server
    # Add http:// prefix, if missing.
    if not url.startswith("http"):
        url = format("http://{}".format(url))

    # Add the /adv suffix.
    url = format("{}/adv".format(url))

    response, info = fetch_url(module, url, method="get")
    if info["status"] != 200:
        return (None, {"msg": info["msg"]})

    try:
        adv_json = json.loads(response.read())
    except ValueError as exc:
        return None, {"msg": str(exc)}

    return adv_json, None


def generate_config(module, pin_cfg):
    """ Creates the config to be used when binding a group of devices.
    Return: <pin> <config> <error> """

    # No servers, so there is nothing to do here.
    if "servers" not in pin_cfg or len(pin_cfg["servers"]) == 0:
        return None, None, None

    nbde_servers = []
    for server in pin_cfg["servers"]:
        adv, err = download_adv(module, server)
        if err:
            return None, None, err
        json_cfg = {"url": server, "adv": adv}
        nbde_servers.append(json_cfg)

    # Multiple servers -> sss pin.
    if len(pin_cfg["servers"]) > 1:
        cfg = {"t": pin_cfg["threshold"], "pins": {"tang": nbde_servers}}
        return "sss", json.dumps(cfg), None

    # Single server -> tang pin.
    cfg = nbde_servers[0]
    return "tang", json.dumps(cfg), None


def parse_keyslots_luks1(luks_dump):
    """ Lists the used keyslots in a LUKS1 device. These may or may not be
    bound to clevis.
    Return: <used keyslots> <error> """

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
    """ Lists the used keyslots in a LUKS2 device. These may or may not be
    bound to clevis.
    Return: <used keyslots> <error> """

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
    """ Lists the used keyslots in a LUKS device. These may or may not be
    bound to clevis.
    Return: <used keyslots> <error> """

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
    """ Lists the clevis-bound slots in a LUKS device.
    Return: <bound slots> <error> """

    slots, err = keyslots_in_use(module, device)
    if err:
        return None, err

    # Now let's iterate through these slots and collect the bound ones.
    bound = []
    for slot in slots:
        _, err = is_slot_bound(module, device, slot)
        if err:
            continue
        bound.append(slot)
    return bound, None


def decrypt_jwe(module, jwe):
    """ Attempt to decrypt JWE.
    Return: <decrypted JWE> <error> """

    args = ["clevis", "decrypt"]
    ret, decrypted, err = module.run_command(args, data=jwe, binary_data=True)
    if ret != 0:
        return None, {"msg": err}
    return decrypted, None


def run_cryptsetup(module, args, **kwargs):
    """ Run cryptsetup command.
    Return: <output> <error> """

    passphrase = kwargs.get("passphrase", None)
    is_keyfile = kwargs.get("is_keyfile", False)
    data = kwargs.get("data", None)

    # Let's check if this is a privileged operation.
    if passphrase is None:
        # No passphrase required, just run the command.
        ret, out, err = module.run_command(args, data=data, binary_data=True)
        if ret != 0:
            errmsg = "Command {} failed: {}".format(" ".join(args), err)
            return None, {"msg": errmsg}
        return out, None

    # This is privileged operation, so we need to provide either a passphrase
    # of a key file.
    if is_keyfile:
        args.extend(["--key-file", passphrase])
        ret, out, err = module.run_command(args, data=data, binary_data=True)
        if ret != 0:
            errmsg = "Command {} failed: {}".format(" ".join(args), err)
            return None, {"msg": errmsg}
        return out, None

    # Regular passphrase here.
    if data is None:
        data = passphrase
    else:
        data = "{}\n{}".format(passphrase, data)

    ret, out, err = module.run_command(args, data=data, binary_data=True)
    if ret != 0:
        errmsg = "Command {} failed: {}".format(" ".join(args), err)
        return None, {"msg": errmsg}
    return out, None


def valid_passphrase(module, **kwargs):
    """ Tests whether the given passphrase is valid for the specified device.
    Return: <boolean> <error> """

    for req in ["device", "passphrase"]:
        if req not in kwargs:
            errmsg = "valid_passphrase: {} is a required parameter".format(req)
            return False, {"msg": errmsg}

    is_keyfile = kwargs.get("is_keyfile", False)
    slot = kwargs.get("slot", None)

    args = ["cryptsetup", "open", "--test-passphrase", kwargs["device"]]
    if slot is not None:
        args.extend(["--key-slot", str(slot)])

    _, err = run_cryptsetup(
        module, args, passphrase=kwargs["passphrase"], is_keyfile=is_keyfile
    )
    if err:
        errmsg = "valid_passphrase: We need a valid passphrase for {}".format(
            kwargs["device"]
        )
        return False, {"msg": errmsg, "err": err}
    return True, None


def retrieve_passphrase(module, device):
    """ Attempt to retrieve a valid passphrase from a clevis-bound device.
    Return: <slot> <passphrase> <error> """

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

        _, err = valid_passphrase(module, device=device, passphrase=decrypted)
        if err:
            continue
        return slot, decrypted, None

    return None, None, {"msg": "No passphrase retrieved"}


def save_slot_luks1(module, **kwargs):
    """ Saves a given data to a specific LUKS1 device and slot. The last
    parameter indicated whether we should overwrite existing metadata.
    Return: <saved> <error> """

    for req in ["device", "slot", "data", "overwrite"]:
        if req not in kwargs:
            return False, {"msg": "{} is a required parameter".format(req)}

    if len(kwargs["data"]) == 0:
        return False, {"msg": "We need data to save to a slot"}

    bound, _ = is_slot_bound(module, kwargs["device"], kwargs["slot"])

    backup, err = backup_luks1_device(module, kwargs["device"])
    if err:
        return False, err

    if bound:
        if not kwargs["overwrite"]:
            errmsg = "{}:{} is already bound and no overwrite set".format(
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
        ret_code, _, stderr = module.run_command(args, binary_data=True)
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
    ret_code, _, stderr = module.run_command(
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
        errmsg = "Error adding JWE to {}:{} ; no changes performed".format(
            kwargs["device"], kwargs["slot"]
        )
        return False, {"msg": errmsg}

    return True, None


def backup_luks1_device(module, device):
    """ Backup LUKSmeta metadata from LUKS1 device, as it can be corrupted when
    saving new metadata.
    Return: <backup> <error> """

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
    """ Restore LUKSmeta metadata from the specified backup.
    Return: <error> """

    args = ["luksmeta", "init", "-f", "-d", device]
    ret_code, _, stderr = module.run_command(args)
    if ret_code != 0:
        return {"msg": stderr}

    for slot in backup:
        _, err = save_slot_luks1(
            module, device=device, slot=slot, data=backup[slot], overwrite=True
        )
        if err:
            return err

    return None


def backup_luks2_token(module, device, token_id):
    """ Backup LUKS2 token, as we may need to restore the metadata.
    Return: <backup> <error> """

    args = ["cryptsetup", "token", "export", "--token-id", token_id, device]
    ret, token, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": "Error during token backup: {}".format(err)}

    try:
        token_json = json.loads(token)
    except ValueError as exc:
        return None, {"msg": str(exc)}
    return token_json, None


def import_luks2_token(module, device, token):
    """ Restore LUKS2 token.
    Return: <error> """

    if not token or len(token) == 0:
        return {"msg": "import_luks2_token: Invalid token"}

    args = ["cryptsetup", "token", "import", device, "--debug"]
    try:
        token_str = json.dumps(token)
    except ValueError as exc:
        return {"msg": str(exc)}

    ret, _, err = module.run_command(args, data=token_str, binary_data=True)
    if ret != 0:
        errmsg = "Error importing token: {}, token: {}".format(err, token)
        return {"msg": errmsg}
    return None


def make_luks2_token(slot, data):
    """ Prepare a JSON LUKS2 token for a given slot.
    Return <token> <error> """

    try:
        metadata = {"type": "clevis", "keyslots": [str(slot)], "jwe": json.loads(data)}
    except ValueError as exc:
        return False, {"msg": "Error making new token: {}".format(str(exc))}

    return metadata, None


def format_jwe(module, data, is_compact):
    """ Format JWE to be saved in a LUKS2 token.
    Return <jwe> <error> """

    args = ["jose", "jwe", "fmt", "--input=-"]
    if is_compact:
        args.append("--compact")
    ret, jwe, err = module.run_command(args, data=data, binary_data=True)
    if ret != 0:
        return None, {"msg": err}
    return jwe, None


def save_slot_luks2(module, **kwargs):
    """ Saves a given data to a specific LUKS2 device and slot. The last
    parameter indicates whether we should overwrite existing metadata.
    Return: <saved> <error> """

    for req in ["device", "slot", "data", "overwrite"]:
        if req not in kwargs:
            return False, {"msg": "{} is a required parameter".format(req)}

    if len(kwargs["data"]) == 0:
        return False, {"msg": "We need data to save to a slot"}

    old_data, token_id, err = get_jwe_luks2(module, kwargs["device"], kwargs["slot"])

    if not err:
        if not kwargs["overwrite"]:
            errmsg = "{}:{} is already bound and no overwrite set".format(
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
        ret_code, _, err = module.run_command(args)
        if ret_code != 0:
            return False, {"msg": "Error removing token: {}".format(err)}

    jwe, err = format_jwe(module, kwargs["data"], False)
    if err:
        import_luks2_token(module, kwargs["device"], old_data)
        return False, {"msg": "Error preparing JWE: {}".format(err["msg"])}

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
    jwe, _ = format_jwe(module, kwargs["data"], True)
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
        errmsg = "Error storing token: {} / {}".format(kwargs["data"], metadata)
        return False, {"msg": errmsg}

    return True, None


def save_slot(module, **kwargs):
    """ Saves data to a specific LUKS device and slot.
    Return <saved> <error> """

    for req in ["device", "slot", "data", "overwrite"]:
        if req not in kwargs:
            return False, {"msg": "{} is a required parameter".format(req)}

    luks, err = get_luks_type(module, kwargs["device"])
    if err:
        return False, err

    if luks == "luks1":
        return save_slot_luks1(module, **kwargs)
    return save_slot_luks2(module, **kwargs)


def is_keyslot_in_use(module, device, slot):
    """ Returns a boolean indicating whether a given slot is in use by a LUKS
    device. This does not mean the slot is clevis-bound necessarily.
    Return: <boolean> """

    slots, err = keyslots_in_use(module, device)
    if err:
        return False
    return str(slot) in slots


def set_passphrase(module, **kwargs):
    """ Adds or replace a LUKS passphrase in a give slot.
    Return: <result> <error> """

    for req in ["device", "slot", "valid_passphrase", "new_passphrase"]:
        if req not in kwargs:
            return False, {"msg": "{} is a required parameter".format(req)}

    is_keyfile = kwargs.get("is_keyfile", False)

    # Make sure we actually have a valid password for this device.
    _, err = valid_passphrase(
        module,
        device=kwargs["device"],
        passphrase=kwargs["valid_passphrase"],
        is_keyfile=is_keyfile,
    )

    if err:
        errmsg = "We need a valid passphrase for {}".format(kwargs["device"])
        return False, {"msg": errmsg}

    # Now let's identify whether this is an in-place change, i.e., if
    # the valid passphrase we have is for the slot we are replacing.
    _, err = valid_passphrase(
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
        _, err = run_cryptsetup(
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
        _, err = run_cryptsetup(
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
    """ Unbind slot in a LUKS1 device. This involves removing both the clevis
    metadata in LUKSMeta as well as its associated keyslot.
    Return <result> <error> """
    _, err = get_jwe_luks1(module, device, slot)
    if err:
        errmsg = "{}:{} is not bound to clevs".format(device, slot)
        return False, {"msg": errmsg}

    cmds = []
    cmds.append(["cryptsetup", "luksKillSlot", "--batch-mode", device, str(slot)])
    cmds.append(
        ["luksmeta", "wipe", "-f", "-d", device, "-u", CLEVIS_UUID, "-s", str(slot)]
    )

    for args in cmds:
        ret, _, err = module.run_command(args)
        if ret != 0:
            return False, {"msg": err}
    return True, None


def unbind_slot_luks2(module, device, slot):
    """ Unbind slot in a LUKS2 device. This involves removing both the clevis
    metadata as well as its associated keyslot.
    Retrurn <result> <error> """
    _, token_id, err = get_jwe_luks2(module, device, slot)
    if err:
        errmsg = "{}:{} is not bound to clevs".format(device, slot)
        return False, {"msg": errmsg}

    cmds = []
    cmds.append(["cryptsetup", "luksKillSlot", "--batch-mode", device, str(slot)])
    cmds.append(["cryptsetup", "token", "remove", "--token-id", token_id, device])

    for args in cmds:
        ret, _, err = module.run_command(args)
        if ret != 0:
            return False, {"msg": err}
    return True, None


def unbind_slot(module, device, slot):
    """ Unbind slot in a LUKS device. This involves removing the clevis
    metadata as well as its associated passphrase.
    Return: <result> <error> """

    luks, err = get_luks_type(module, device)
    if err:
        return False, err

    if luks == "luks1":
        return unbind_slot_luks1(module, device, slot)
    return unbind_slot_luks2(module, device, slot)


def new_key(module, device):
    """ Generate a new key with the same entropy as the LUKS master key.
    Return <key> <error> """

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
        errmsg = "new_key: Unable to find entropy bits for {}".format(device)
        return None, {"msg": errmsg}
    bits = match.groups()[0]
    args = ["pwmake", bits]
    ret, key, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": stderr}
    return key.rstrip(), None


def new_pass_jwe(module, device, pin, pin_cfg):
    """ Generates a new pass and returns it and it encrypted with the specified
    pin.
    Return: <pass> <jwe> <error> """

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
    """ Checks whether we can use this slot for binding clevis.
    Return <result> <error> """

    # Check if valid LUKS device.
    _, err = get_luks_type(module, device)
    if err:
        return False, err

    bound, _ = is_slot_bound(module, device, slot)
    if bound and not overwrite:
        errmsg = "{}:{} is already bound and no overwrite set".format(device, slot)
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
    """ Discard a passphrase from the LUKS device.
    Return <result> <error> """

    for req in ["device", "passphrase"]:
        if req not in kwargs:
            return False, {"msg": "{} is a required parameter".format(req)}

    passphrase = kwargs["passphrase"]
    args = ["cryptsetup", "luksRemoveKey", "--batch-mode", kwargs["device"]]
    is_keyfile = kwargs.get("is_keyfile", False)
    if is_keyfile:
        args.append(passphrase)
        passphrase = None
    ret, _, err = module.run_command(args, data=passphrase, binary_data=True)
    if ret != 0:
        return False, {"msg": "Error removing passphrase: {}".format(err)}
    return True, None


def prepare_to_rebind(module, device, slot):
    """ Backups metadata from device and also remove it, in preparation for a
    rebind operation.
    Return <backup> <error> """

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
        _, token_id, err = get_jwe_luks2(module, device, slot)
        if err:
            return err
        backup, err = backup_luks2_token(module, device, token_id)
        if err:
            return None, err
        args = ["cryptsetup", "token", "remove", "--token-id", token_id, device]

    ret, _, err = module.run_command(args)
    if ret != 0:
        return None, {"msg": err}
    return backup, None


def restore_failed_rebind(module, device, backup):
    """ Restore metadata after a failed rebind operation.
    Return <error> """

    luks_type, err = get_luks_type(module, device)
    if err:
        return None, err

    if luks_type == "luks1":
        return restore_luks1_device(module, device, backup)
    return import_luks2_token(module, device, backup)


def bind_slot(module, **kwargs):
    """ Create a clevis binding in a given LUKS device.
    Return <result> <error> """

    for req in ["device", "slot", "auth", "auth_cfg"]:
        if req not in kwargs:
            return False, {"msg": "{} is a required parameter".format(req)}

    overwrite = kwargs.get("overwrite", True)
    discard_pw = kwargs.get("discard_passphrase", False)

    _, err = can_bind_slot(module, kwargs["device"], kwargs["slot"], overwrite)
    if err:
        return False, err

    if "passphrase" not in kwargs or kwargs["passphrase"] is None:

        if discard_pw:
            errmsg = "You cannot discard a passphrase you did not provide"
            return False, {"msg": errmsg}

        _, passphrase, err = retrieve_passphrase(module, kwargs["device"])
        if err:
            return False, err
        # We retrieved a passphrase from an existing binding, so let's use it.
        is_keyfile = False

    else:
        passphrase = kwargs["passphrase"]
        is_keyfile = kwargs.get("is_keyfile", False)

    # At this point we can proceed to bind.
    key, jwe, err = new_pass_jwe(
        module, kwargs["device"], kwargs["auth"], kwargs["auth_cfg"]
    )
    if err:
        return False, err

    bound, _ = is_slot_bound(module, kwargs["device"], kwargs["slot"])

    if bound:
        backup, err = prepare_to_rebind(module, kwargs["device"], kwargs["slot"])
        if err:
            return False, err

    # We add the key first because it will be referenced by the metadata.
    _, err = set_passphrase(
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

    _, err = save_slot(
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


def bindings_sanity_check(bindings, data_dir):
    """ Performs sanity-checking on the bindings list and related arguments.
    Return: <bindings> <error> """

    errstate = 'state in a group of devices must be "present" or "absent"'

    if not bindings:
        return None, {"msg": "No devices set"}

    for idx, dev_group in enumerate(bindings):
        # Set up the operation.
        if "state" not in dev_group:
            bindings[idx]["state"] = "present"
        else:
            if dev_group["state"] not in ["present", "absent"]:
                return None, {"msg": errstate}
        # Make sure we have the required information for the devices.
        for didx, device in enumerate(dev_group["devices"]):
            if "path" not in device:
                errmsg = "Each device must have a path set"
                return None, {"msg": errmsg}

            bindings[idx]["devices"][didx]["path"] = cmd_quote(device["path"])

            if "keyfile" in device:
                basefile = os.path.basename(device["keyfile"])
                keyfile = os.path.join(data_dir, basefile)
                bindings[idx]["devices"][didx]["keyfile"] = cmd_quote(keyfile)

        if "auth" not in dev_group:
            if dev_group["state"] != "absent":
                errmsg = "We need auth configuration when state is not absent"
                return None, {"msg": errmsg}
            # Adding the one information we need for unbind.
            bindings[idx]["auth"] = {"slot": 1}
            continue

        # Make sure we have the list of servers properly set.
        if "servers" not in dev_group["auth"]:
            bindings[idx]["auth"]["servers"] = list()

        # The defaults for the auth attributes.
        auth_defaults = {
            "slot": 1,
            "threshold": 1,
            "overwrite": False,
            "discard_passphrase": False,
        }

        for attr in auth_defaults:
            if attr not in dev_group["auth"]:
                bindings[idx]["auth"][attr] = auth_defaults[attr]

    return bindings, None


def process_bindings(module, bindings):
    """ Process the list of bindings and performs the appropriate operations.
    Return: <result> """

    original_bindings = bindings
    result = {"changed": False, "original_bindings": bindings}
    if module.check_mode:
        return result

    for dev_group in bindings:
        state = dev_group["state"]
        if state != "absent":
            auth_name, cfg, err = generate_config(module, dev_group["auth"])
            if err:
                NbdeClientClevisError(dict(msg=err))

        slot = dev_group["auth"]["slot"]
        for device in dev_group["devices"]:
            if dev_group["state"] == "absent":
                _, err = is_slot_bound(module, device["path"], slot)
                if err:
                    # Slot not bound, moving on.
                    continue
                _, err = unbind_slot(module, device["path"], slot)
            else:
                overwrite = dev_group["auth"]["overwrite"]
                bound, _ = is_slot_bound(module, device["path"], slot)
                if bound and not overwrite:
                    result["msg"] = "{}:{} is bound and no overwrite set".format(
                        device["path"], slot
                    )
                    continue

                passphrase = device.get("pass", None)
                discard_pw = dev_group["auth"].get("discard_passphrase", False)
                if not passphrase:
                    passphrase = device.get("keyfile", None)
                is_keyfile = "keyfile" in device

                _, err = bind_slot(
                    module,
                    device=device["path"],
                    slot=slot,
                    auth=auth_name,
                    auth_cfg=cfg,
                    passphrase=passphrase,
                    is_keyfile=is_keyfile,
                    overwrite=overwrite,
                    discard_passphrase=discard_pw,
                )

            if err:
                err["original_bindings"] = original_bindings
                raise NbdeClientClevisError(err)
            result["changed"] = True

    return result


def run_module():
    """ The entry point of the module. """

    module_args = dict(
        bindings=dict(type="list", required=False),
        data_dir=dict(type="str", required=False),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    params = module.params

    bindings, err = bindings_sanity_check(params["bindings"], params["data_dir"])
    if err:
        err["changed"] = False
        result = err
    else:
        result = process_bindings(module, bindings)

    result["original_bindings"] = params["bindings"]
    module.exit_json(**result)


def main():
    """ The main function! """
    run_module()


if __name__ == "__main__":
    main()

# vim:set ts=4 sw=4 et:
