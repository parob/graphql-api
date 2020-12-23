.. _types:

.. highlight:: python

Types
=====

ObjectQL supports all of the core GraphQL types.

+-------------------+--------------------+
| Python Type       | GraphQL Type       |
+===================+====================+
| int               | Int                |
+-------------------+--------------------+
| float             | Float              |
+-------------------+--------------------+
| str               | String             |
+-------------------+--------------------+
| bool              | Boolean            |
+-------------------+--------------------+
| Class             | Object             |
+-------------------+--------------------+
| Enum              | Enum               |
+-------------------+--------------------+
| NoneType          | null               |
+-------------------+--------------------+

ObjectQL also includes convenient mappings for some common Python types.

+-------------------+--------------------+
| Python Type       | GraphQL Type       |
+===================+====================+
| UUID              | UUID               |
+-------------------+--------------------+
| datetime          | DateTime           |
+-------------------+--------------------+
| dict, list        | JSON               |
+-------------------+--------------------+

Type Mapping
------------



Object type
```````````


Interface type
``````````````


Enum type
`````````

The Enum type is a scalar type that is restricted to a set of values.

In ObjectQL you can define Enum types with Python Enums

.. code-block:: python

    import enum

    class BookGenre(enum.Enum):
        thriller = "thriller"
        romance = "romance"
        fantasy = "fantasy"


List type modifier
``````````````````

The Python **List** type hint is used to indicate that a field returns a List.
It can be used to wrap type types, scalars and enums and other modifiers.

.. code-block:: python
    :emphasize-lines: 10

    from typing import List
    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    @schema.type(root=True)
    class RootType:

        @schema.field
        def user_names(self) -> List[str]:
          return ["Tom", "Steve"]


Non-nullable type modifier
``````````````````````````

The Python **Optional** type hint is used to indicate that a field could return a null value.
It can be used to wrap type types, scalars and enums and other modifiers.

.. code-block:: python
    :emphasize-lines: 10

    from typing import Optional
    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    @schema.type(root=True)
    class RootType:

        @schema.field
        def get_user_id(self, email: str) -> Optional[str]:
          if email == "rob@rob.com":
            return "1234"
          return None

Union type modifier
```````````````````

The Python **Union** type hint is used to indicate that a field has a Union modifier.
It can be used to wrap multiple type types.

.. code-block:: python
    :emphasize-lines: 10

    from typing import Union
    from objectql import ObjectQLSchema

    schema = ObjectQLSchema()

    @schema.type(root=True)
    class RootType:

        @schema.field
        def get_home(self, name: str) -> Union[Flat, House]:
            if name == "Phil":
                return House()
            return Flat()


Custom types
````````````
