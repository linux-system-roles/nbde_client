Changelog
=========

[1.3.4] - 2025-06-23
--------------------

### Bug Fixes

- fix: Adjust for Ansible 2.19 (#206)

### Other Changes

- ci: Add support for bootc end-to-end validation tests (#204)
- ci: Use ansible 2.19 for fedora 42 testing; support python 3.13 (#205)

[1.3.3] - 2025-05-21
--------------------

### Other Changes

- ci: ansible-plugin-scan is disabled for now (#187)
- ci: bump ansible-lint to v25; provide collection requirements for ansible-lint (#190)
- refactor: fix python black formatting (#191)
- ci: Check spelling with codespell (#192)
- ci: Add test plan that runs CI tests and customize it for each role (#193)
- ci: In test plans, prefix all relate variables with SR_ (#194)
- ci: Fix bug with ARTIFACTS_URL after prefixing with SR_ (#195)
- ci: several changes related to new qemu test, ansible-lint, python versions, ubuntu versions (#197)
- ci: use tox-lsr 3.6.0; improve qemu test logging (#198)
- ci: skip storage scsi, nvme tests in github qemu ci (#199)
- ci: bump sclorg/testing-farm-as-github-action from 3 to 4 (#200)
- ci: bump tox-lsr to 3.8.0; rename qemu/kvm tests (#201)
- ci: Add Fedora 42; use tox-lsr 3.9.0; use lsr-report-errors for qemu tests (#202)

[1.3.2] - 2025-01-09
--------------------

### Other Changes

- ci: bump codecov/codecov-action from 4 to 5 (#183)
- ci: Use Fedora 41, drop Fedora 39 (#184)
- ci: Use Fedora 41, drop Fedora 39 - part two (#185)

[1.3.1] - 2024-10-30
--------------------

### Other Changes

- ci: Add tft plan and workflow (#169)
- ci: Update fmf plan to add a separate job to prepare managed nodes (#171)
- ci: bump sclorg/testing-farm-as-github-action from 2 to 3 (#172)
- ci: Add workflow for ci_test bad, use remote fmf plan (#173)
- ci: Fix missing slash in ARTIFACTS_URL (#174)
- chore: add debian late boot support (#176)
- ci: Add tags to TF workflow, allow more [citest bad] formats (#177)
- ci: ansible-test action now requires ansible-core version (#178)
- ci: add YAML header to github action workflow files (#179)
- refactor: Use vars/RedHat_N.yml symlink for CentOS, Rocky, Alma wherever possible (#181)

[1.3.0] - 2024-07-02
--------------------

### New Features

- feat: Allow initrd configuration to be skipped (#165)

### Bug Fixes

- fix: add support for EL10 (#166)

### Other Changes

- test: some files not created by nm implementation (#164)
- ci: ansible-lint action now requires absolute directory (#167)

[1.2.20] - 2024-06-11
--------------------

### Other Changes

- ci: use tox-lsr 3.3.0 which uses ansible-test 2.17 (#159)
- ci: tox-lsr 3.4.0 - fix py27 tests; move other checks to py310 (#161)
- ci: Add supported_ansible_also to .ansible-lint (#162)

[1.2.19] - 2024-04-22
--------------------

### Other Changes

- refactor: clear net config from initrd via NM config (#156)

[1.2.18] - 2024-04-04
--------------------

### Other Changes

- ci: bump codecov/codecov-action from 3 to 4 (#149)
- ci: fix python unit test - copy pytest config to tests/unit (#151)
- ci: bump ansible/ansible-lint from 6 to 24 (#152)
- ci: bump mathieudutour/github-tag-action from 6.1 to 6.2 (#153)

[1.2.17] - 2024-01-16
--------------------

### Other Changes

- ci: bump actions/github-script from 6 to 7 (#143)
- ci: bump github/codeql-action from 2 to 3 (#144)
- ci: bump actions/setup-python from 4 to 5 (#145)
- ci: Use supported ansible-lint action; run ansible-lint against the collection (#146)
- ci: Use supported ansible-lint action; run ansible-lint against the collection (#147)

[1.2.16] - 2023-10-23
--------------------

### Other Changes

- chore: Add support for AlmaLinux 8 & 9 (#133)
- Bump actions/checkout from 3 to 4 (#134)
- ci: ensure dependabot git commit message conforms to commitlint (#137)
- ci: use dump_packages.py callback to get packages used by role (#139)
- ci: tox-lsr version 3.1.1 (#141)

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
