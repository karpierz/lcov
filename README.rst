lcov
====

Graphical front-end for GCC's coverage testing tool gcov.

Overview
========

|package_bold| is a strict Python implementation of the `LCOV`_ package.

LCOV is an extension of GCOV, a GNU tool which provides information about
what parts of a program are actually executed (i.e. "covered") while running
a particular test case. The extension consists of a set of scripts which build
on the textual GCOV output to implement the following enhanced functionality:

  * HTML based output: coverage rates are additionally indicated using bar
    graphs and specific colors.

  * Support for large projects: overview pages allow quick browsing of
    coverage data by providing three levels of detail: directory view,
    file view and source code view.

LCOV was initially designed to support Linux kernel coverage measurements,
but works as well for coverage measurements on standard user space applications.

`PyPI record`_.

`Documentation`_.

Usage
-----

TBD...

Installation
============

Prerequisites:

+ Python 3.7 or higher

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
.. _LCOV: https://github.com/linux-test-project/lcov
