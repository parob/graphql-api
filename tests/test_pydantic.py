import unittest
from typing import Optional, List

from pydantic import BaseModel, Field

from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field
from graphql import graphql_sync, GraphQLSchema


class NestedModel(BaseModel):
    nested_field: str = Field(description="A nested field")

class OptionalModel(BaseModel):
    optional_field: Optional[str] = Field(description="An optional field")
    another_optional_field: Optional[int]

class Statistics(BaseModel):
    conversations_count: int = Field(description="Number of conversations")
    messages_count: int
    completion_rate: Optional[float]
    nested_stats: NestedModel
    optional_nested: Optional[NestedModel]
    list_of_nested: List[NestedModel]
    list_of_optional_nested: Optional[List[OptionalModel]]


class PydanticAPI(GraphQLAPI):
    @field
    def get_stats(self) -> Statistics:
        return Statistics(
            conversations_count=10,
            messages_count=25,
            completion_rate=0.85,
            nested_stats=NestedModel(nested_field="test_value"),
            optional_nested=NestedModel(nested_field="optional_test"),
            list_of_nested=[NestedModel(nested_field="item1"), NestedModel(nested_field="item2")],
            list_of_optional_nested=[OptionalModel(optional_field="opt_item1", another_optional_field=None)]
        )

    @field
    def get_stats_optional_missing(self) -> Statistics:
        return Statistics(
            conversations_count=5,
            messages_count=12,
            completion_rate=None,
            nested_stats=NestedModel(nested_field="another_value"),
            optional_nested=None,
            list_of_nested=[NestedModel(nested_field="item_a")],
            list_of_optional_nested=None
        )

    @field
    def get_optional_model_present(self) -> OptionalModel:
        return OptionalModel(optional_field="present", another_optional_field=123)

    @field
    def get_optional_model_none(self) -> OptionalModel:
        return OptionalModel(optional_field=None, another_optional_field=None)

    @field
    def get_optional_model_partial(self) -> OptionalModel:
        return OptionalModel(optional_field=None, another_optional_field=456)


class TestPydanticMapping(unittest.TestCase):
    def setUp(self):
        # PydanticAPI class contains the root fields.
        # We create a GraphQLAPI instance, configuring PydanticAPI as its root_type.
        self.configured_api = GraphQLAPI(root_type=PydanticAPI)
        # Then, we build the schema from this configured API instance.
        self.schema = self.configured_api.build_schema()[0]

    def test_pydantic_model_mapping(self):
        query = '''
            query {
                getStats {
                    conversationsCount
                    messagesCount
                    completionRate
                    nestedStats {
                        nestedField
                    }
                    optionalNested {
                        nestedField
                    }
                    listOfNested {
                        nestedField
                    }
                    listOfOptionalNested {
                        optionalField
                        anotherOptionalField
                    }
                }
            }
        '''
        expected_result = {
            'getStats': {
                'conversationsCount': 10,
                'messagesCount': 25,
                'completionRate': 0.85,
                'nestedStats': {'nestedField': 'test_value'},
                'optionalNested': {'nestedField': 'optional_test'},
                'listOfNested': [{'nestedField': 'item1'}, {'nestedField': 'item2'}],
                'listOfOptionalNested': [{'optionalField': 'opt_item1', 'anotherOptionalField': None}]
            }
        }
        result = graphql_sync(self.schema, query)
        self.assertIsNone(result.errors)
        self.assertEqual(result.data, expected_result)

    def test_pydantic_model_optional_fields_missing(self):
        query = '''
            query {
                getStatsOptionalMissing {
                    conversationsCount
                    messagesCount
                    completionRate
                    nestedStats {
                        nestedField
                    }
                    optionalNested {
                        nestedField
                    }
                    listOfNested {
                        nestedField
                    }
                    listOfOptionalNested {
                        optionalField
                    }
                }
            }
        '''
        expected_result = {
            'getStatsOptionalMissing': {
                'conversationsCount': 5,
                'messagesCount': 12,
                'completionRate': None,  # Expect None as it's optional and not provided
                'nestedStats': {'nestedField': 'another_value'},
                'optionalNested': None, # Expect None as it's optional and not provided
                'listOfNested': [{'nestedField': 'item_a'}],
                'listOfOptionalNested': None # Expect None as it's optional and not provided
            }
        }
        result = graphql_sync(self.schema, query)
        self.assertIsNone(result.errors)
        self.assertEqual(result.data, expected_result)

    def test_optional_model_fields(self):
        query_present = '''
            query {
                getOptionalModelPresent {
                    optionalField
                    anotherOptionalField
                }
            }
        '''
        expected_present = {'getOptionalModelPresent': {'optionalField': 'present', 'anotherOptionalField': 123}}
        result_present = graphql_sync(self.schema, query_present)
        self.assertIsNone(result_present.errors)
        self.assertEqual(result_present.data, expected_present)

        query_none = '''
            query {
                getOptionalModelNone {
                    optionalField
                    anotherOptionalField
                }
            }
        '''
        expected_none = {'getOptionalModelNone': {'optionalField': None, 'anotherOptionalField': None}}
        result_none = graphql_sync(self.schema, query_none)
        self.assertIsNone(result_none.errors)
        self.assertEqual(result_none.data, expected_none)

        query_partial = '''
            query {
                getOptionalModelPartial {
                    optionalField
                    anotherOptionalField
                }
            }
        '''
        # Pydantic defaults optional_field to None if not provided
        expected_partial = {'getOptionalModelPartial': {'optionalField': None, 'anotherOptionalField': 456}}
        result_partial = graphql_sync(self.schema, query_partial)
        self.assertIsNone(result_partial.errors)
        self.assertEqual(result_partial.data, expected_partial)

    def test_pydantic_model_descriptions(self):
        # Test if descriptions from Pydantic Field are carried over
        stats_type = self.schema.get_type("Statistics")
        self.assertEqual(stats_type.description, None) # Class docstring is not used by default with pydantic
        self.assertEqual(stats_type.fields['conversationsCount'].description, "Number of conversations")
        # Fields without explicit description in Pydantic Field should have None
        self.assertEqual(stats_type.fields['messagesCount'].description, None)

        nested_type = self.schema.get_type("NestedModel")
        self.assertEqual(nested_type.fields['nestedField'].description, "A nested field")

        optional_type = self.schema.get_type("OptionalModel")
        self.assertEqual(optional_type.fields['optionalField'].description, "An optional field")
        self.assertEqual(optional_type.fields['anotherOptionalField'].description, None)


if __name__ == '__main__':
    unittest.main()
