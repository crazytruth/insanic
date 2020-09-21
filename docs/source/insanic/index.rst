Insanic
=================================

Welcome to Insanic's Documentation.
Insanic is framework to make your life easier when
developing for a microservice architecture.
Insanic extends `Sanic <https://github.com/huge-success/sanic>`_, a Python 3.6+ web server
and web framework that's written to go fast.  Although Sanic lays
down the basics of a server, we needed a little more in terms
of easier and centralized service integration.  A framework
that allowed developers to concentrate on the business logic
without the need to fret over minor details when
considering deploying a fully functioning application in a
production environment.

Since the goal of this framework was deployment into a
microservice system, most features are for the simplification of
either communicating with another service, or for helping with
the automation of deploying the Insanic based application.


Background
----------

This project's inception was when I was working for my
former employer. We were tasked with migrating a
legacy monolithic application, written with Django 1.6 and
Python 2.7, to a fully microservice based system in a
limited time frame.

We only had a handful of Python developers to achieve this task
so we needed a framework to rapidly migrate business logic.
As a result, most design decisions were based on my experience with
`Django <https://www.djangoproject.com/>`_ and
`Django REST Framework <http://www.django-rest-framework.org/>`_.
Anyone planning to use Insanic will recognize similarities
in certain parts of the framework.


Prerequisites
-------------

Because this largely based on Sanic, for the basics,
you should have prior knowledge of Sanic.
Please refer to
`Sanic's Documentation <https://sanic.readthedocs.io/en/latest/>`_
for more information.


.. note::

    Insanic only supports Sanic version 19.12 and forward.
    Plan is to only support the previous major updates but
    is subject to change.
