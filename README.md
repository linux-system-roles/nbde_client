nbde_client
-----------

Ansible role for configuring Network-Bound Disk Encryption clients (e.g. clevis).

This role currently supports `clevis` as a provider and it uses it for operations like encryption
and decryption.


Supported Distributions
-----------------------
* RHEL-7+, CentOS-7+
* Fedora


Limitations
-----------
This role can currently create `tang` bindings. TPM2 is not supported as of now.


Role Variables
--------------

These are the variables that can be passed to the role:


| **Variable** | **Default/Choices** | **Description** |
|----------|-------------|------|
| `nbde_client_provider` | `clevis`| identifies the provider for the `nbde_client` role. We currently support `clevis`.|
| `nbde_client_bindings` | | a list containing binding configurations, which include e.g. devices and slots.
|`nbde_client_remote_dir` | `/root/.local/share/nbde_client/` |  specifies a directory in the remote hosts that may be used for storing temporary data such as transferred keyfiles. |
|`nbde_client_update_initramfs` | `yes` | indicates whether the initramfs should be updated in case changes are made when processing the clevis operations on the devices.|


#### nbde_client_bindings
`nbde_client_bindings` supports the following keys:
| **Name** | **Default/Choices** | **Description** |
|----------|-------------|------|
| `device` | | specifies the path of a LUKS device (**REQUIRED**). |
| `state` | **present** / absent | specifies whether a binding with the configuration described should be added or removed. Setting state to present (the default) means a binding will be added; setting state to absent means a binding will be removed from the device/slot. |
| `slot` | `1` | specifies the slot to use for the binding. |
| `servers` | |  specifies a list of servers to bind to. To enable high availability, simply specify more than one server here. |
| `threshold` | `1` | specifies the threshold for the Shamir Secret Sharing (SSS) scheme that is put in place when using more than one server. When using multiple servers, threshold indicates how many of those servers should succeed, in terms of decryption, in order to complete the process of recovering the LUKS passphrase to open the device. |
| `discard_passphrase` | `no` | specifies whether we should discard the passphrase provided -- via either pass or keyfile, in devices from the LUKS device, after completing the binding operation. |


Example:
```yaml
nbde_client_bindings:
  - device: /dev/sda1
    keyfile: /vault/keyfile
    state: present
    slot: 2
    threshold: 1
    discard_passphrase: no
    servers:
      - http://server1.example.com
      - http://server2.example.com
```

Example Playbooks
----------------
#### Example 1: high availability

```yaml
---
- hosts: all

  vars:
    nbde_client_bindings:
      - device: /dev/sda1
        pass: password
        servers:
          - http://server1.example.com
          - http://server2.example.com
  roles:
    - linux-system-roles.nbde_client
```

#### Example 2: remove binding from slot 2 in /dev/sda1
```yaml
---
- hosts: all

  vars:
    nbde_client_bindings:
      - device: /tmp/sda1
        pass: password
        slot: 2
        state: absent

  roles:
    - linux-system-roles.nbde_client
```


License
-------

MIT
