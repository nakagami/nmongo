==========
nmongo
==========

MongoDB client for CPython and MicroPython.

It has mongo Shell like APIs.

Requirement
------------

- MongoDB 3.2, 3.4
- CPython 3.4+ https://www.python.org or MicroPython https://micropython.org 

Install
----------

CPython
::

   $ python3 -m pip install nmongo


MicroPython
::

    $ micropython -m upip install micropython-errno
    $ micropython -m upip install micropython-os
    $ micropython -m upip install micropython-socket
    $ micropython -m upip install micropython-time
    $ micropython -m upip install micropython-datetime
    $ micropython -m upip install micropython-binascii
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
   {'price': 50, '_id': ObjectId("5826b2313d28909ce9f6ea63"), 'name': 'banana'}
   >>> cur = db.fruits.find()
   >>> cur.fetchall()
   [{'price': 200, '_id': ObjectId("5826b2273d28909ce9f6ea61"), 'name': 'apple'}, {'price': 100, '_id': ObjectId("5826b2313d28909ce9f6ea62"), 'name': 'orange'}, {'price': 50, '_id': ObjectId("5826b2313d28909ce9f6ea63"), 'name': 'banana'}]
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

Count each collection records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

   >>> for collection in db.getCollections():
   ...     print(collection.name, collection.count())
   ...
   fruits 3
   >>> db.getCollection('fruits').count()
   3
   >>>

See also mongo Shell Methods (Collection and Database sections).

- https://docs.mongodb.com/manual/reference/method/#collection
- https://docs.mongodb.com/manual/reference/method/#database

Features Not Implemented
--------------------------

Common
~~~~~~~~

- GridFS
- ssl

MicroPython
~~~~~~~~~~~~

- datetime.datetime
- time.struct_time
