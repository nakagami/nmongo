==========
nmongo
==========

MongoDB client for CPython and MicroPython.

It has mongo Shell like APIs.

Requirement
------------

- MongoDB 3.2
- CPython 3.4+ https://www.python.org or MicroPython https://micropython.org 

Install
----------

CPython
::

   $ pip install nmongo


MicroPython
::

    $ micropython -m upip install micropython-errno
    $ micropython -m upip install micropython-os
    $ micropython -m upip install micropython-time
    $ micropython -m upip install micropython-datetime
    $ micropython -m upip install micropython-binascii
    $ micropython -m upip install micropython-decimal
    $ micropython -m upip install micropython-random
    $ micropython -m upip install nmongo


Example
-----------

Connect to Database
~~~~~~~~~~~~~~~~~~~~

::

   >>> import nmongo
   >>> db = nmongo.connect('servername', 'somewhatdatabase')
   >>>

Create
~~~~~~~

::

   >>> db.fruits.insert({'name': 'apple', 'price': 200})
   1
   >>> db.fruits.insert([{'name': 'orange', 'price': 100}, {'name': 'banana', 'price': 50}])
   2
   >>> db.fruits.count()
   3
   >>>

Read
~~~~~~~

::

   >>> cur = db.fruits.find({'name': 'banana'})
   >>> cur.fetchone()
   {'_id': ObjectId("5823dd6d3d28909ce9f6e99c"), 'name': 'banana', 'price': 50}
   >>> cur.fetchone()
   >>>

Update
~~~~~~~

::

   >>> db.fruits.update({'name': 'banana'}, {'$inc': {'price': 20}})
   {'nModified': 1, 'ok': 1, 'n': 1}
   >>> cur = db.fruits.find({'name': 'banana'})
   >>> cur.fetchone()
   {'_id': ObjectId("5823dd6d3d28909ce9f6e99c"), 'name': 'banana', 'price': 70}
   >>>


Delete
~~~~~~~

::

   >>> db.fruits.remove({'name': 'banana'})
   1
   >>> db.fruits.count()
   2

See also mongo Shell Methods (Collection and Database sections).

- https://docs.mongodb.com/manual/reference/method/#collection
- https://docs.mongodb.com/manual/reference/method/#database

Features Not Implemented
--------------------------

Common
~~~~~~~~

- ssl

MicroPython
~~~~~~~~~~~~

- datetime.datetime
- time.struct_time
