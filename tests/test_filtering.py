from objectql.decorators import query, mutation, interface
from objectql.mapper import GraphQLMetaKey
from objectql.schema import GraphQLSchemaBuilder


class TestSchemaFiltering:

    def test_query_remove_invalid(self):
        api = GraphQLSchemaBuilder()

        class Person:

            def __init__(self):
                self.name = ""

            @mutation
            def update_name(self, name: str) -> 'Person':
                self.name = name
                return self

        class Root:

            @query
            def person(self) -> Person:
                return Person()

        api.root = Root
        executor = api.executor()

        test_query = '''
            query PersonName {
                person {
                    updateName(name:"phil") {
                        name
                    }
                }
            }
        '''

        result = executor.execute(test_query)
        assert result.errors
        assert 'Cannot query field' in result.errors[0].message

    def test_mutation_return_query(self):
        """
        Mutation fields by default should return queries
        :return:
        """
        api = GraphQLSchemaBuilder()

        class Person:

            def __init__(self):
                self._name = ""

            @query
            def name(self) -> str:
                return self._name

            @mutation
            def update_name(self, name: str) -> 'Person':
                self._name = name
                return self

        class Root:

            @query
            def person(self) -> Person:
                return Person()

        api.root = Root
        executor = api.executor()

        test_query = '''
            mutation PersonName {
                person {
                    updateName(name:"phil") {
                        name
                    }
                }
            }
        '''

        result = executor.execute(test_query)
        assert not result.errors

        expected = {
            "person": {
                "updateName": {
                    "name": "phil"
                }
            }
        }

        assert result.data == expected

    def test_keep_interface(self):
        api = GraphQLSchemaBuilder()

        @interface
        class Person:

            @query
            def name(self) -> str:
                pass

        class Employee(Person):

            def __init__(self):
                self._name = "Bob"

            @query
            def name(self) -> str:
                return self._name

            @query
            def department(self) -> str:
                return "Human Resources"

            @mutation
            def set_name(self, name: str) -> str:
                self._name = name
                return name

        bob_employee = Employee()

        class Root:

            @query
            def person(self) -> Person:
                return bob_employee

        api.root = Root
        executor = api.executor()

        test_query = '''
            query PersonName {
                person {
                    name
                    ... on Employee {
                        department
                    }
                }
            }
        '''

        test_mutation = '''
            mutation SetPersonName {
                person {
                    ... on EmployeeMutable {
                        setName(name: "Tom")
                    }
                }
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "person": {
                "name": "Bob",
                "department": "Human Resources"
            }
        }

        expected_2 = {
            "person": {
                "name": "Tom",
                "department": "Human Resources"
            }
        }

        assert result.data == expected

        result = executor.execute(test_mutation)

        assert not result.errors

        result = executor.execute(test_query)

        assert result.data == expected_2

    def test_remove_interface(self):
        api = GraphQLSchemaBuilder()

        @interface
        class RenamablePerson:

            @mutation
            def set_name(self, name: str) -> str:
                pass

        class Employee(RenamablePerson):

            def __init__(self):
                self.name = "Bob"

            @query
            def name(self) -> str:
                return self.name

            @query
            def department(self) -> str:
                return "Human Resources"

            @mutation
            def set_name(self, name: str) -> str:
                self.name = name
                return name

        bob_employee = Employee()

        class Root:

            @query
            def person(self) -> RenamablePerson:
                return bob_employee

        api.root = Root
        executor = api.executor()

        test_mutation = '''
            mutation SetPersonName {
                person {
                    ... on EmployeeMutable {
                        setName(name: "Tom")
                    }
                }
            }
        '''

        result = executor.execute(test_mutation)

        expected = {
            "person": {
                "setName": "Tom"
            }
        }

        assert result.data == expected

        test_query = '''
            query PersonName {
                person {
                    name
                }
            }
        '''

        result = executor.execute(test_query)

        assert 'Cannot query field "person" on type "PlaceholderQuery".' == result.errors[0].message

    def test_mutation_return_mutable_flag(self):
        api = GraphQLSchemaBuilder()

        class Person:

            def __init__(self):
                self._name = ""

            @query
            def name(self) -> str:
                return self._name

            @mutation
            def update_name(self, name: str) -> 'Person':
                self._name = name
                return self

            @mutation({GraphQLMetaKey.resolve_to_mutable: True})
            def update_name_mutable(self, name: str) -> 'Person':
                self._name = name
                return self

        class Root:

            @query
            def person(self) -> Person:
                return Person()

        api.root = Root
        executor = api.executor()

        test_query = '''
                    mutation PersonName {
                        person {
                            updateName(name:"phil") {
                                name
                            }
                        }
                    }
                '''

        result = executor.execute(test_query)
        assert not result.errors

        expected = {
            "person": {
                "updateName": {
                    "name": "phil"
                }
            }
        }

        assert result.data == expected

        test_mutable_query = '''
                    mutation PersonName {
                        person {
                            updateNameMutable(name:"tom") {
                                updateName(name:"phil") {
                                    name
                                }
                            }
                        }
                    }
                '''

        result = executor.execute(test_mutable_query)
        assert not result.errors

        expected = {
            "person": {
                "updateNameMutable": {
                    "updateName": {
                        "name": "phil"
                    }
                }
            }
        }

        assert result.data == expected

        test_invalid_query = '''
                    mutation PersonName {
                        person {
                            updateName(name:"tom") {
                                updateName(name:"phil") {
                                    name
                                }
                            }
                        }
                    }
                '''

        result = executor.execute(test_invalid_query)
        assert result.errors
        assert 'Cannot query field "updateName"' in result.errors[0].message

        test_invalid_mutable_query = '''
                    mutation PersonName {
                        person {
                            updateNameMutable(name:"tom") {
                                name
                            }
                        }
                    }
                '''

        result = executor.execute(test_invalid_mutable_query)
        assert result.errors
        assert 'Cannot query field "name"' in result.errors[0].message
