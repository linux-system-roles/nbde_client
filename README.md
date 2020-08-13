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
| `nbde_client_bindings` | | a list containing binding configurations, which include e.g. devices and slots. |


#### nbde_client_bindings
`nbde_client_bindings` is a list of dictionaries that support the following keys:
| **Name** | **Default/Choices** | **Description** |
|----------|-------------|------|
| `device` | | specifies the path of the backing device of an encrypted device on the managed host. This device must be already configured as a LUKS device before using the role (**REQUIRED**). |
| `encryption_password` | | a valid password or passphrase for opening/unlocking the specified device. Recommend vault encrypting the value. See https://docs.ansible.com/ansible/latest/user_guide/vault.html |
| `encryption_key_src` | | either the absolute or relative path, on the control node, of a file containing an encryption key valid for opening/unlocking the specified device.  The role will copy this file to the managed node(s). |
| `state` | **present** / absent | specifies whether a binding with the configuration described should be added or removed. Setting state to present (the default) means a binding will be added; setting state to absent means a binding will be removed from the device/slot. |
| `slot` | `1` | specifies the slot to use for the binding. |
| `servers` | |  specifies a list of servers to bind to. To enable high availability, specify more than one server here. |
| `threshold` | `1` | specifies the threshold for the Shamir Secret Sharing (SSS) scheme that is put in place when using more than one server. When using multiple servers, threshold indicates how many of those servers should succeed, in terms of decryption, in order to complete the process of recovering the LUKS passphrase to open the device. |
| `password_temporary` | `no` | If yes, the password or passphrase that was provided via the `encryption_password` or `encryption_key` arguments will be used to unlock the device and then it will be removed from the LUKS device after the binding operation completes, i.e. it will not be valid anymore. To be used if device has been previously created with a dummy password or passphrase (for example by an automated install like kickstart that set up some sort of "default" password), which the role should replace by a stronger one. |


Example:
```yaml
nbde_client_bindings:
  - device: /dev/sda1
    encryption_key_src: /vault/keyfile
    state: present
    slot: 2
    threshold: 1
    password_temporary: no
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
        # recommend vault encrypting the encryption_password
        # see https://docs.ansible.com/ansible/latest/user_guide/vault.html
        encryption_password: password
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
      - device: /dev/sda1
        # recommend vault encrypting the encryption_password
        # see https://docs.ansible.com/ansible/latest/user_guide/vault.html
        encryption_password: password
        slot: 2
        state: absent

  roles:
    - linux-system-roles.nbde_client
```


License
-------

MIT
