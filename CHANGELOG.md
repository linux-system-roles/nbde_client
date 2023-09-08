Changelog
=========

[1.2.15] - 2023-09-08
--------------------

### Other Changes

- ci: Add markdownlint, test_converting_readme, and build_docs workflows (#129)

  - markdownlint runs against README.md to avoid any issues with
    converting it to HTML
  - test_converting_readme converts README.md > HTML and uploads this test
    artifact to ensure that conversion works fine
  - build_docs converts README.md > HTML and pushes the result to the
    docs branch to publish dosc to GitHub pages site.
  - Fix markdown issues in README.md
  
  Signed-off-by: Sergei Petrosian <spetrosi@redhat.com>

- docs: Make badges consistent, run markdownlint on all .md files (#130)

  - Consistently generate badges for GH workflows in README RHELPLAN-146921
  - Run markdownlint on all .md files
  - Add custom-woke-action if not used already
  - Rename woke action to Woke for a pretty badge
  
  Signed-off-by: Sergei Petrosian <spetrosi@redhat.com>

- ci: Remove badges from README.md prior to converting to HTML (#131)

  - Remove thematic break after badges
  - Remove badges from README.md prior to converting to HTML
  
  Signed-off-by: Sergei Petrosian <spetrosi@redhat.com>


[1.2.14] - 2023-07-19
--------------------

### Bug Fixes

- fix: facts being gathered unnecessarily (#127)

### Other Changes

- docs: Consistent contributing.md for all roles - allow role specific contributing.md section (#120)
- ci: update tox-lsr to version 3.0.0 (#121)
- ci: Add pull request template and run commitlint on PR title only (#122)
- ci: Rename commitlint to PR title Lint, echo PR titles from env var (#123)
- ci: fix python 2.7 CI tests by manually installing python2.7 package (#124)
- ci: ansible-lint - ignore var-naming[no-role-prefix] (#125)
- ci: ansible-test ignores file for ansible-core 2.15 (#126)

[1.2.13] - 2023-04-27
--------------------

### Other Changes

- test: check generated files for ansible_managed, fingerprint
- ci: Add commitlint GitHub action to ensure conventional commits with feedback

[1.2.12] - 2023-04-13
--------------------

### Other Changes

- remove unused symlink; fix ansible-lint handler issue (#113)

[1.2.11] - 2023-04-07
--------------------

### Other Changes

- Add README-ansible.md to refer Ansible intro page on linux-system-roles.github.io (#110)
- Use templates instead of files for ansible_managed (#111)

[1.2.10] - 2023-01-23
--------------------

### New Features

- none

### Bug Fixes

- Fix nbde_client error handling (#101)

### Other Changes

- none

[1.2.9] - 2023-01-19
--------------------

### New Features

- none

### Bug Fixes

- Do not report password in stacktrace or return value from module (#98)
- Use daemon_reload with askpass path service (#96)

### Other Changes

- Cleanup non-inclusive words.
- ansible-lint 6.x fixes (#92)

[1.2.8] - 2022-11-29
--------------------

### New Features

- none

### Bug Fixes

- use fedora.linux_system_roles.nbde_server for tests (#86)

use fedora.linux_system_roles.nbde_server for tests instead of git
cloning the repo.  Use the `tests/collection-requirements.yml` so
the test infrastructure will install the collection.

### Other Changes

- none

[1.2.7] - 2022-11-01
--------------------

### New Features

- none

### Bug Fixes

- correct clevis askpass unit conditional (#81)

- Add default clevis luks askpass unit (#79)

skip clevis askpass systemd unit for RHEL 8.2 and 8.3

- use no_log: true where secrets might be revealed

### Other Changes

- fix test tmp files (#80)

tests - use generated temp directory for all controller files

If you run multiple tests in parallel, some of the tests could overwrite
or remove files in use by other tests on the controller.  Use a
temp directory for controller files.

- test support for CentOS Stream 9

[1.2.6] - 2022-07-28
--------------------

### New Features

- none

### Bug Fixes

- Sets needed spacing for appended rd.neednet parameter (#68)

* Sets proper spacing for parameter rd.neednet=1 so that it is correctly appended to kernel cmdline, changes = to += for adding rd.neednet parameter

### Other Changes

- changelog_to_tag action - github action ansible test improvements

- Use GITHUB_REF_NAME as name of push branch; fix error in branch detection [citest skip] (#76)

We need to get the name of the branch to which CHANGELOG.md was pushed.

Signed-off-by: Rich Megginson <rmeggins@redhat.com>

[1.2.5] - 2022-07-19
--------------------

### New Features

- none

### Bug Fixes

- none

### Other Changes

- make all tests work with gather_facts: false (#69)

Ensure tests work when using ANSIBLE_GATHERING=explicit

- make min_ansible_version a string in meta/main.yml (#70)

The Ansible developers say that `min_ansible_version` in meta/main.yml
must be a `string` value like `"2.9"`, not a `float` value like `2.9`.

- Add CHANGELOG.md (#71)

[1.2.4] - 2022-05-06
--------------------

### New Features

- none

### Bug Fixes

- none

### Other Changes

- bump tox-lsr version to 2.11.0; remove py37; add py310

[1.2.3] - 2022-04-19
--------------------

### New Features

- support gather\_facts: false; support setup-snapshot.yml

### Bug Fixes

- none

### Other Changes

- none

[1.2.2] - 2022-03-31
--------------------

### New Features

- none

### Bug Fixes

- network-flush: reset autoconnect-priority to zero

### Other Changes

- none

[1.2.1] - 2022-03-29
--------------------

### New Features

- Add dracut module for disabling autoconnect within initrd

### Bug Fixes

- none

### Other Changes

- bump tox-lsr version to 2.10.1

[1.2.0] - 2022-01-13
--------------------

### New Features

- none

### Bug Fixes

- Add network flushing before setting up network

### Other Changes

- none

[1.1.2] - 2022-01-10
--------------------

### New Features

- none

### Bug Fixes

- none

### Other Changes

- bump tox-lsr version to 2.8.3
- change recursive role symlink to individual role dir symlinks

[1.1.1] - 2021-11-08
--------------------

### New Features

- support python 39, ansible-core 2.12, ansible-plugin-scan
- add regenerate-all to the dracut command 

### Bug Fixes

- none

### Other Changes

- update tox-lsr version to 2.7.1
- make role work with ansible-core-2.11 ansible-lint and ansible-test
- use tox-lsr version 2.5.1

[1.1.0] - 2021-08-10
--------------------

### New Features

- Drop support for Ansible 2.8 by bumping the Ansible version to 2.9

### Bug Fixes

- none

### Other Changes

- none

[1.0.4] - 2021-06-08
--------------------

### New Features

- none

### Bug Fixes

- fix python black formatting errors

### Other Changes

- none

[1.0.3] - 2021-04-08
--------------------

### New Features

- none

### Bug Fixes

- Fix issues found by ansible-test and linters - enable all tests on all repos - remove suppressions
- Fix ansible-test errors

### Other Changes

- Remove python-26 environment from tox testing
- README.md - Adding a blank line after nbde\_client\_bindings
- update to tox-lsr 2.4.0 - add support for ansible-test with docker
- Increase memory of tests
- CI: Add support for RHEL-9

[1.0.2] - 2021-02-11
--------------------

### New Features

- Add centos8

### Bug Fixes

- Fix centos6 repos; use standard centos images

### Other Changes

- use tox-lsr 2.2.0
- use molecule v3, drop v2
- support jinja 2.7
- remove ansible 2.7 support from molecule
- use tox for ansible-lint instead of molecule
- use new tox-lsr plugin
- use github actions instead of travis

[1.0.1] - 2020-10-31
--------------------

### New Features

- none

### Bug Fixes

- none

### Other Changes

- meta/main.yml: CI add support for Fedora 33
- lock ansible-lint version at 4.3.5; suppress role name lint warning
- sync collections related changes from template to nbde\_client role

[1.0.0] - 2020-08-13
--------------------

### Initial Release
