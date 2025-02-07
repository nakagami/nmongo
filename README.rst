==========
nmongo
==========

Azure Cosmos DB for MongoDB client for CPython and MicroPython.

It has mongo shell like APIs.

Support platform
------------------

- CPython 3.11+ https://www.python.org
- MicroPython

Install
----------

CPython

::

   $ python3 -m pip install nmongo


MicroPython

Go interactive shell and install with mip as follow.

::

   >>> import mip
   >>> mip.install("datetime")
   >>> mip.install(""https://github.com/nakagami/nmongo/blob/master/nmongo.py"")

Example
-----------


Connect to Azure CosmosDB
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


::

   >>> import nmongo
   >>> db = nmongo.connect('xxx.mongo.cosmos.azure.com', 'somewhatdatabase', user='xxx', password='password', port=10255, use_ssl=True)
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

This driver uses OP_COMMNAD OP_COMMANDREPLY, which was added in MongoDB3.2 and removed in MongoDB 4.2.
These documents have been removed too from the official documentation. Please let me know if there is any good documentation left somewhere.

Features Not Implemented
--------------------------

- GridFS
