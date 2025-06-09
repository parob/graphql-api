from typing import Optional, List, Any
import inspect # Ensure inspect is imported

import pytest
from pydantic import BaseModel, Field, RootModel
from graphql import graphql_sync, GraphQLSchema as CoreGraphQLSchema

from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field

# Models for testing (Copied from previous correct state)

class EmptyModel(BaseModel):
    pass

class AliasedModel(BaseModel):
    actual_name: str = Field(alias="name_in_data")

class AnyFieldModel(BaseModel):
    anything: Any
    optional_any: Optional[Any]

class ModelD(BaseModel):
    final_value: int

class ModelC(BaseModel):
    model_d: ModelD
    optional_model_d: Optional[ModelD]

class ModelB(BaseModel):
    model_c: ModelC

class ModelA(BaseModel):
    model_b: ModelB
    name: str

class ListPrimitivesModel(BaseModel):
    str_list: List[str]
    optional_int_list: Optional[List[int]]
    list_optional_str: List[Optional[str]]
    optional_list_optional_int: Optional[List[Optional[int]]]

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
    list_of_optional_nested: Optional[List[OptionalModel]] = Field(default=None)

# Renamed TestAPI to PydanticTestAPI to avoid Pytest collection warning
class PydanticTestAPI(GraphQLAPI):
    def __init__(self):
        super().__init__(root_type=PydanticTestAPI) # Use the new class name

    @field
    def get_stats(self) -> Statistics:
        return Statistics(
            conversations_count=10, messages_count=25, completion_rate=0.85,
            nested_stats=NestedModel(nested_field="test_value"),
            optional_nested=NestedModel(nested_field="optional_test"),
            list_of_nested=[NestedModel(nested_field="item1"), NestedModel(nested_field="item2")],
            list_of_optional_nested=[OptionalModel(optional_field="opt_item1", another_optional_field=None)]
        )

    @field
    def get_stats_optional_missing(self) -> Statistics:
        return Statistics(
            conversations_count=5, messages_count=12, completion_rate=None,
            nested_stats=NestedModel(nested_field="another_value"),
            optional_nested=None, list_of_nested=[NestedModel(nested_field="item_a")],
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

    @field
    def get_empty_model(self) -> EmptyModel:
        return EmptyModel()

    @field
    def get_aliased_model(self) -> AliasedModel:
        return AliasedModel.model_validate({'name_in_data': 'aliased value'})

    # @field
    # def get_any_field_model(self) -> AnyFieldModel:
    #     return AnyFieldModel(anything={"complex": [1, "data"], "bool": True}, optional_any=None)

    @field
    def get_deeply_nested_model(self) -> ModelA:
        return ModelA(
            name="TestA", model_b=ModelB(model_c=ModelC(
                model_d=ModelD(final_value=123), optional_model_d=ModelD(final_value=456)))
        )

    @field
    def get_deeply_nested_optional_missing(self) -> ModelA:
        return ModelA(
            name="TestAOptional", model_b=ModelB(model_c=ModelC(
                model_d=ModelD(final_value=789), optional_model_d=None))
        )

    @field
    def get_list_primitives(self) -> ListPrimitivesModel:
        return ListPrimitivesModel(
            str_list=["a", "b", "c"], optional_int_list=[1, 2, 3],
            list_optional_str=["x", None, "y"], optional_list_optional_int=[10, None, 20]
        )

    @field
    def get_list_primitives_optionals_none(self) -> ListPrimitivesModel:
        return ListPrimitivesModel(
            str_list=[], optional_int_list=None,
            list_optional_str=[None, None], optional_list_optional_int=None
        )

# Pytest Fixture
@pytest.fixture(scope="function")
def gql_schema_and_root():
    api_instance = PydanticTestAPI() # Use the renamed class
    schema = api_instance.build_schema()[0]
    return schema, api_instance

# Execute Query Helper
def execute_query(schema_and_root, query: str, variables: Optional[dict] = None):
    schema, root_value = schema_and_root
    result = graphql_sync(schema, query, root_value=root_value, variable_values=variables)
    if result.errors:
        # print("GraphQL Errors:", result.errors)
        raise result.errors[0]
    return result.data

# --- Test Functions (adapted to use gql_schema_and_root) ---

def test_pydantic_model_mapping(gql_schema_and_root: tuple):
    query = '''
        query { getStats {
            conversationsCount messagesCount completionRate
            nestedStats { nestedField }
            optionalNested { nestedField }
            listOfNested { nestedField }
            listOfOptionalNested { optionalField anotherOptionalField }
        } }
    '''
    expected = {
        'getStats': {
            'conversationsCount': 10, 'messagesCount': 25, 'completionRate': 0.85,
            'nestedStats': {'nestedField': 'test_value'},
            'optionalNested': {'nestedField': 'optional_test'},
            'listOfNested': [{'nestedField': 'item1'}, {'nestedField': 'item2'}],
            'listOfOptionalNested': [{'optionalField': 'opt_item1', 'anotherOptionalField': None}]
        }
    }
    assert execute_query(gql_schema_and_root, query) == expected

def test_pydantic_model_optional_fields_missing(gql_schema_and_root: tuple):
    query = '''
        query { getStatsOptionalMissing {
            conversationsCount messagesCount completionRate
            nestedStats { nestedField }
            optionalNested { nestedField }
            listOfNested { nestedField }
            listOfOptionalNested { optionalField }
        } }
    '''
    expected = {
        'getStatsOptionalMissing': {
            'conversationsCount': 5, 'messagesCount': 12, 'completionRate': None,
            'nestedStats': {'nestedField': 'another_value'},
            'optionalNested': None, 'listOfNested': [{'nestedField': 'item_a'}],
            'listOfOptionalNested': None
        }
    }
    assert execute_query(gql_schema_and_root, query) == expected

def test_optional_model_fields(gql_schema_and_root: tuple):
    query_present = '{ getOptionalModelPresent { optionalField anotherOptionalField } }'
    assert execute_query(gql_schema_and_root, query_present) == \
        {'getOptionalModelPresent': {'optionalField': 'present', 'anotherOptionalField': 123}}

    query_none = '{ getOptionalModelNone { optionalField anotherOptionalField } }'
    assert execute_query(gql_schema_and_root, query_none) == \
        {'getOptionalModelNone': {'optionalField': None, 'anotherOptionalField': None}}

    query_partial = '{ getOptionalModelPartial { optionalField anotherOptionalField } }'
    assert execute_query(gql_schema_and_root, query_partial) == \
        {'getOptionalModelPartial': {'optionalField': None, 'anotherOptionalField': 456}}

def test_pydantic_model_descriptions(gql_schema_and_root: tuple):
    schema, _ = gql_schema_and_root
    stats_type = schema.get_type("Statistics")
    assert stats_type.description == inspect.cleandoc(Statistics.__doc__)
    assert stats_type.fields['conversationsCount'].description == "Number of conversations"
    assert stats_type.fields['messagesCount'].description is None

    nested_type = schema.get_type("NestedModel")
    assert nested_type.fields['nestedField'].description == "A nested field"

    optional_type = schema.get_type("OptionalModel")
    assert optional_type.fields['optionalField'].description == "An optional field"
    assert optional_type.fields['anotherOptionalField'].description is None

def test_empty_model(gql_schema_and_root: tuple):
    query = '{ getEmptyModel { __typename } }'
    assert execute_query(gql_schema_and_root, query) == {'getEmptyModel': {'__typename': 'EmptyModel'}}
    schema, _ = gql_schema_and_root
    empty_gql_type = schema.get_type("EmptyModel")
    assert empty_gql_type is not None
    assert not empty_gql_type.fields

def test_aliased_model(gql_schema_and_root: tuple):
    query = '{ getAliasedModel { actualName } }'
    expected = {'getAliasedModel': {'actualName': 'aliased value'}}
    assert execute_query(gql_schema_and_root, query) == expected
    schema, _ = gql_schema_and_root
    aliased_gql_type = schema.get_type("AliasedModel")
    assert "actualName" in aliased_gql_type.fields
    assert "nameInData" not in aliased_gql_type.fields

# def test_any_field_model(gql_schema_and_root: tuple):
#     query = '{ getAnyFieldModel { anything optionalAny } }'
#     expected = {'getAnyFieldModel': {'anything': {"complex": [1, "data"], "bool": True}, 'optionalAny': None}}
#     assert execute_query(gql_schema_and_root, query) == expected

#     schema, _ = gql_schema_and_root
#     any_field_model_gql_type = schema.get_type("AnyFieldModel")
#     assert any_field_model_gql_type is not None, "AnyFieldModel not found in schema"
#     assert "anything" in any_field_model_gql_type.fields, "'anything' field missing"
#     assert any_field_model_gql_type.fields["anything"].type.name == "JSON"
#     assert any_field_model_gql_type.fields["optionalAny"].type.name == "JSON"

def test_deeply_nested_model(gql_schema_and_root: tuple):
    query = '''
        query {
            getDeeplyNestedModel { name modelB { modelC { modelD { finalValue } optionalModelD { finalValue } } } }
            getDeeplyNestedOptionalMissing { name modelB { modelC { modelD { finalValue } optionalModelD { finalValue } } } }
        }
    '''
    expected = {
        'getDeeplyNestedModel': {
            'name': "TestA", 'modelB': {'modelC': {'modelD': {'finalValue': 123}, 'optionalModelD': {'finalValue': 456}}}
        },
        'getDeeplyNestedOptionalMissing': {
            'name': "TestAOptional", 'modelB': {'modelC': {'modelD': {'finalValue': 789}, 'optionalModelD': None}}
        }
    }
    assert execute_query(gql_schema_and_root, query) == expected

def test_list_primitives(gql_schema_and_root: tuple):
    query_present = ''' query GetLP { getListPrimitives {
        strList optionalIntList listOptionalStr optionalListOptionalInt
    } } '''
    expected_present = {
        'getListPrimitives': {
            'strList': ["a", "b", "c"], 'optionalIntList': [1, 2, 3],
            'listOptionalStr': ["x", None, "y"], 'optionalListOptionalInt': [10, None, 20]
        }
    }
    assert execute_query(gql_schema_and_root, query_present) == expected_present

    query_optionals_none = ''' query GetLPNone { getListPrimitivesOptionalsNone {
        strList optionalIntList listOptionalStr optionalListOptionalInt
    } } '''
    expected_optionals_none = {
        'getListPrimitivesOptionalsNone': {
            'strList': [], 'optionalIntList': None,
            'listOptionalStr': [None, None], 'optionalListOptionalInt': None
        }
    }
    assert execute_query(gql_schema_and_root, query_optionals_none) == expected_optionals_none
