..

Contributing to Insanic
========================

Thank you for considering to contribute to Insanic.


Setup for development
-----------------------

-   Fork Insanic to your GitHub account.
-   `Clone`_ the Insanic repository locally.

    .. code-block:: text

        $ git clone https://github.com/crazytruth/insanic
        $ cd insanic

-   Add your fork as a remote to push your work to. Replace
    ``{username}`` with your username. This names the remote "fork", the
    default crazytruth remote is "origin".

    .. code-block:: text

        git remote add fork https://github.com/{username}/insanic

-   Create a virtualenv with `pyenv`_ and `pyenv-virtualenv`_.

    -   Prerequisites for creating a virtualenv

        Please install `pyenv`_ and `pyenv-virtualenv`_ if you dont have them
        installed.

        You must also install the Python versions with :code:`pyenv`.

        .. code-block:: bash

            # to view available python versions
            $ pyenv install --list

            # to install python 3.6.12
            $ pyenv install 3.6.12

    Now to settings the virtual environment.

    Replace ``{pythonversion}`` with the python version to
    create the virtual environment in.

    .. code-block:: bash

        $ pyenv virtualenv {pythonversion} insanic
        $ pyenv local insanic

-   Install Insanic in editable mode with development dependencies.

    .. code-block:: text

        $ pip install -e . -r requirements/dev.txt

-   Install the pre-commit hooks.

    .. code-block:: text

        $ pre-commit install

.. _pyenv: https://github.com/pyenv/pyenv
.. _pyenv-virtualenv: https://github.com/pyenv/pyenv-virtualenv
.. _Fork: https://github.com/crazytruth/insanic/fork
.. _Clone: https://help.github.com/en/articles/fork-a-repo#step-2-create-a-local-clone-of-your-fork


Start coding
--------------

-   Create a branch to identify the issue you would like to work on. If
    you're submitting a bug or documentation fix, branch off of the
    latest ".x" branch.

    .. code-block:: text

        $ git fetch origin
        $ git checkout -b your-branch-name origin/1.1.x

    If you're submitting a feature addition or change, branch off of the
    "master" branch.

    .. code-block:: text

        $ git fetch origin
        $ git checkout -b your-branch-name origin/master

-   Using your favorite editor, make your changes,
    `committing as you go`_.
-   Include tests that cover any code changes you make. Make sure the
    test fails without your patch. Run the tests as described below.
-   Push your commits to your fork on GitHub and
    `create a pull request`_. Link to the issue being addressed with
    ``fixes #123`` in the pull request.

    .. code-block:: text

        $ git push --set-upstream fork your-branch-name

.. _committing as you go: https://dont-be-afraid-to-commit.readthedocs.io/en/latest/git/commandlinegit.html#commit-your-changes
.. _create a pull request: https://help.github.com/en/articles/creating-a-pull-request


Running the tests
--------------------

Run the basic test suite with pytest.

.. code-block:: text

    $ pytest

This runs the tests for the current environment, which is usually
sufficient. CI will run the full suite when you submit your pull
request. You can run the full test suite with tox if you don't want to
wait.

.. code-block:: text

    $ tox


Running test coverage
--------------------------

Generating a report of lines that do not have test coverage can indicate
where to start contributing. Run ``pytest`` using ``coverage`` and
generate a report.

.. code-block:: text

    $ pip install coverage
    $ coverage run -m pytest
    $ coverage html

Open ``htmlcov/index.html`` in your browser to explore the report.

Read more about `coverage <https://coverage.readthedocs.io>`__.


Building the docs
--------------------

Build the docs in the ``docs`` directory using Sphinx.

.. code-block:: text

    $ cd docs
    $ make html

Open ``build/html/index.html`` in your browser to view the docs.

Read more about `Sphinx <https://www.sphinx-doc.org/en/stable/>`__.

To recompile requirements
-------------------------

All requirements for development, tests, and documentation are
in :doc:`requirements` directory.

To recompile requirements. Add the requirements to :code:`*.in`

.. code-block::

    $ cd requirements
    $ pip-compile dev.in


Reference for this document
-----------------------------

- Flask Contributing Documentation: https://github.com/pallets/flask/blob/master/CONTRIBUTING.rst
