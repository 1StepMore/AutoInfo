name: Bug report
about: Report a bug and link a regression scenario (P1-1 regression flywheel)
title: "[Bug] "
labels: ["bug"]
assignees: ""
body:
  - type: textarea
    id: description
    attributes:
      label: Bug description
      description: Describe the bug clearly and concisely.
      placeholder: "A clear description of what the bug is."
    validations:
      required: true
  - type: textarea
    id: steps-to-reproduce
    attributes:
      label: Steps to reproduce
      description: Steps to reproduce the behavior.
      placeholder: |
        1. Run '...'
        2. Configure '...'
        3. See error '...'
    validations:
      required: true
  - type: textarea
    id: expected-behavior
    attributes:
      label: Expected behavior
      description: What you expected to happen.
    validations:
      required: true
  - type: input
    id: environment
    attributes:
      label: Environment
      description: "OS, Python version, AutoInfo version."
      placeholder: "e.g. Ubuntu 22.04, Python 3.11, AutoInfo v1.8.1"
    validations:
      required: false
  - type: textarea
    id: regression-scenario
    attributes:
      label: "回归场景 (regression scenario)"
      description: |
        Name the validation scenario (in `src/autoinfo/mcp/scenarios/regression/`) that will guard this fix.
        If you haven't created it yet, write "none (will add in PR)".
      placeholder: "e.g. regression-collect-int-id (will add in PR)"
    validations:
      required: true
