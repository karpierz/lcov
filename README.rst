lcov
====

Compile all py files in a wheel to pyc files.

Overview
========

|package_bold| is a strict fork of Grant Patten's pycwheel_ package
with a fixes allowing to work with Python3 or higher and with a code
reformatting and some improvements.

|package_bold| is a graphical front-end for GCC's coverage testing tool gcov.
It collects gcov data for multiple source files and creates HTML pages
containing the source code annotated with coverage information. It also adds
overview pages for easy navigation within the file structure.

`PyPI record`_.

`Documentation`_.

Usage
-----

Processing the wheel in place:

.. code-block:: bash

    $ python -m pyc_wheel your_wheel-1.0.0-py3-none-any.whl
    # Output: your_wheel-1.0.0-py3-none-any.whl

or with backup:

.. code-block:: bash

    $ python -m pyc_wheel --with_backup your_wheel-1.0.0-py3-none-any.whl
    # Output: your_wheel-1.0.0-py3-none-any.whl
    #         your_wheel-1.0.0-py3-none-any.whl.bak

or with quiet:

.. code-block:: bash

    $ python -m pyc_wheel --quiet your_wheel-1.0.0-py3-none-any.whl
    # Output: your_wheel-1.0.0-py3-none-any.whl

Installation
============

Prerequisites:

+ Python 3.6 or higher

  * https://www.python.org/
  * 3.7 is a primary test environment.

+ pip and setuptools

  * https://pypi.org/project/pip/
  * https://pypi.org/project/setuptools/

To install run:

  .. parsed-literal::

    python -m pip install --upgrade |package|

Development
===========

Prerequisites:

+ Development is strictly based on *tox*. To install it run::

    python -m pip install --upgrade tox

Visit `development page`_.

Installation from sources:

clone the sources:

  .. parsed-literal::

    git clone |respository| |package|

and run:

  .. parsed-literal::

    python -m pip install ./|package|

or on development mode:

  .. parsed-literal::

    python -m pip install --editable ./|package|

License
=======

  | Copyright (c) 2020-2022, Adam Karpierz
  | Licensed under the BSD license
  | https://opensource.org/licenses/BSD-3-Clause
  | Please refer to the accompanying LICENSE file.

Authors
=======

* Adam Karpierz <adam@karpierz.net>

.. |package| replace:: lcov
.. |package_bold| replace:: **lcov**
.. |respository| replace:: https://github.com/karpierz/lcov.git
.. _development page: https://github.com/karpierz/lcov
.. _PyPI record: https://pypi.org/project/lcov/
.. _Documentation: https://lcov.readthedocs.io/
