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
| `nbde_client_bindings` | | a list containing groups of LUKS devices and applicable settings for a binding. This group of devices contains specific binding configurations to be applied to the set of devices.
|`nbde_client_remote_dir` | `/root/.local/share/nbde_client/` |  specifies a directory in the remote hosts that may be used for storing temporary data such as transferred keyfiles. |
|`nbde_client_update_initramfs` | `yes` | indicates whether the initramfs should be updated in case changes are made when processing the clevis operations on the devices.|


#### nbde_client_bindings
`nbde_client_bindings` supports the following keys:
| **Name** | **Default/Choices** | **Description** |
|----------|-------------|------|
|`devices` | | specifies LUKS devices, with their path and possibly either a passphrase or key file.|
|`pin` | | the settings for the binding, like the servers it should bind to. |
| `state` | **present** / absent | specifies whether the binding with the configuration described should be added or removed. Setting `state` to `present` (the default) means bindings will be added; setting `state` to `absent` means bindings will be removed from the devices/slots. |


##### devices
`devices` supports the following keys:
| **Name** | **Default/Choices** | **Description** |
|----------|-------------|------|
| `path` | | specifies the path to access this device (**REQUIRED**).|
| `pass`| |  specifies a valid passphrase for this device. |
| `keyfile` | | specifies either the absolute or relative path of a valid key file for this device.

Example:
```yaml
- devices:
    - path: /dev/sda1
      pass: password
    - path: /dev/sda2
      keyfile: /vault/keyfile
```

##### pin
`pin` supports the following keys:
| **Name** | **Default/Choices** | **Description** |
|----------|-------------|------|
| `slot` | `1` | specifies the slot to use for the binding. |
|`servers` | | specifies a list of servers to bind to. To enable high availability, simply specify more than one server here. |
| `threshold` | `1` | specifies the threshold for the Shamir Secret Sharing (SSS) scheme that is put in place when using more than one server. When using multiple servers, `threshold` indicates how many of those servers should succeed in order to complete the decryption.
| `overwrite` | `no` | specifies whether we should override any existing binding in the specified slot.
|`discard_passphrase` |  `no` | specifies whether we should discard the passphrase provided  -- via either `pass` or `keyfile`, in `devices` -- after completing the binding operation.


Example:
```yaml
pin:
  slot: 3
  servers:
    - http://tang.server01
    - http://tang.server02
  overwrite: yes
```


Example Playbooks
----------------
#### Example 1: high availability

```yaml
---
- hosts: all
  become: true

  vars:
    nbde_client_bindings:
      - devices:
          - path: /dev/sda1
            pass: passphrase
        pin:
          servers:
            - http://tang.server01
            - http://tang.server02
  roles:
    - linux-system-roles.nbde_client
```

#### Example 2: remove binding from slot 2
```yaml
---
- hosts: all
  become: true

  vars:
    nbde_client_bindings:
      - devices:
          - path: /dev/sda1
            pass: passphrase
        pin:
          slot: 2
        state: absent
  roles:
    - linux-system-roles.nbde_client
```


License
-------

MIT
