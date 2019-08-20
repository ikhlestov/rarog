============
Contributing
============

Thanks for considering contributing to Rarog.

Support questions
==================

Please, don't use the issue tracker for this. It's faster to ping me directly in Gitter
as `ikhlestov <https://gitter.im/ikhlestov>`__.

Reporting issues
================

- For issue reporting, please, add at least such info:

  - Python version
  - Rarog version
  - ClickHouse version
  - OS you are working with

- Feel free to open a ticket for a feature request

- Before making an issue or feature request, it's better to check what already exists.


Submitting patches
==================

Workflow is pretty straightforward:

1. Make repository fork
2. Clone GitHub repo
3. Make a change
4. Make sure all tests passed
5. Write new tests to support coverage on the same level
6. Commit changes to your forked repository
7. Make pull request from GitHub page for your clone against master branch

Notes:

- Mainly it's better to discuss the feature in issue previously in any case.
- Try to follow the code style. At present there are such requirements:

  - Pep8 compatible code
  - Max line width is 100 symbols
  - `Google-style <https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html#example-google>`__ docstrings

Running tests
-------------

To be able to run tests, you should have docker and tox(optionally) installed.
You can run tests in two ways:

- :code:`./run_tests` - start tests with you current python from the env
- :code:`./run_tests tox` - execute tests under the tox with all supported python versions


    
