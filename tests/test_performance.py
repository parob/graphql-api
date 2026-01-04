"""Performance tests for graphql-api with deeply nested models.

These tests are inspired by real-world patterns from the outeract codebase,
which has deeply nested structures like:
- Organisation -> Application -> User -> UserIdentity -> PlatformConnection (5 levels)
- Event -> Edge -> User/File relationships
- WebhookSubscription -> WebhookDelivery chains
"""
import time
import tracemalloc
from dataclasses import dataclass, field as dataclass_field
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel

from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field


class TestSchemaBuilding:
    """Tests for schema building performance with deeply nested types."""

    def test_deeply_nested_pydantic_5_levels(self) -> None:
        """Test schema building with 5 levels of nesting (like outeract's Org->App->User->Identity->PlatformConnection)."""

        # Level 5: Platform Connection (deepest)
        class PlatformConnection(BaseModel):
            id: str
            platform_name: str
            webhook_url: Optional[str] = None
            config: Dict[str, Any] = {}

        # Level 4: User Identity
        class UserIdentity(BaseModel):
            id: str
            external_id: str
            identity_type: str
            platform_connection: Optional[PlatformConnection] = None

        # Level 3: User
        class User(BaseModel):
            id: str
            name: str
            email: Optional[str] = None
            is_system_user: bool = False
            identities: List[UserIdentity] = []

        # Level 2: Application
        class Application(BaseModel):
            id: str
            name: str
            config: Dict[str, Any] = {}
            users: List[User] = []
            platform_connections: List[PlatformConnection] = []

        # Level 1: Organisation (root)
        class Organisation(BaseModel):
            id: str
            name: str
            applications: List[Application] = []

        class API:
            @field
            def organisations(self) -> List[Organisation]:
                return []

            @field
            def organisation(self, org_id: str) -> Optional[Organisation]:
                return None

        # Measure schema building time
        start_time = time.perf_counter()
        api = GraphQLAPI(root_type=API)
        schema, _ = api.build()
        end_time = time.perf_counter()

        build_time = (end_time - start_time) * 1000  # Convert to ms
        print(f"\n5-level nested schema build time: {build_time:.2f}ms")

        # Verify schema is correctly built
        from graphql import print_schema
        schema_sdl = print_schema(schema)
        assert "Organisation" in schema_sdl
        assert "Application" in schema_sdl
        assert "User" in schema_sdl
        assert "UserIdentity" in schema_sdl
        assert "PlatformConnection" in schema_sdl

        # Performance assertion - should build in under 500ms
        assert build_time < 500, f"Schema build took too long: {build_time:.2f}ms"

    def test_deeply_nested_pydantic_10_levels(self) -> None:
        """Test schema building with 10 levels of nesting - extreme case."""

        class Level10(BaseModel):
            value: str

        class Level9(BaseModel):
            child: Level10
            data: str

        class Level8(BaseModel):
            child: Level9
            data: str

        class Level7(BaseModel):
            child: Level8
            data: str

        class Level6(BaseModel):
            child: Level7
            data: str

        class Level5(BaseModel):
            child: Level6
            data: str

        class Level4(BaseModel):
            child: Level5
            data: str

        class Level3(BaseModel):
            child: Level4
            data: str

        class Level2(BaseModel):
            child: Level3
            data: str

        class Level1(BaseModel):
            child: Level2
            data: str

        class API:
            @field
            def root(self) -> Level1:
                return Level1(
                    data="root",
                    child=Level2(data="l2", child=Level3(data="l3", child=Level4(
                        data="l4", child=Level5(data="l5", child=Level6(
                            data="l6", child=Level7(data="l7", child=Level8(
                                data="l8", child=Level9(data="l9", child=Level10(value="leaf"))
                            ))
                        ))
                    )))
                )

        start_time = time.perf_counter()
        api = GraphQLAPI(root_type=API)
        schema, _ = api.build()
        end_time = time.perf_counter()

        build_time = (end_time - start_time) * 1000
        print(f"\n10-level nested schema build time: {build_time:.2f}ms")

        from graphql import print_schema
        schema_sdl = print_schema(schema)
        for i in range(1, 11):
            assert f"Level{i}" in schema_sdl

        assert build_time < 1000, f"Schema build took too long: {build_time:.2f}ms"

    def test_wide_schema_many_types(self) -> None:
        """Test schema building with many types (width rather than depth)."""

        # Create 50 different model types dynamically
        models = []
        namespace = {"BaseModel": BaseModel, "Dict": Dict, "Any": Any}
        for i in range(50):
            model_code = f"""
class Model{i}(BaseModel):
    id: str
    name: str
    value: int
    metadata: Dict[str, Any] = {{}}
"""
            exec(model_code, namespace)
            models.append(namespace[f"Model{i}"])

        # Create API with all models
        class API:
            pass

        for i, model in enumerate(models):
            def make_field(m):
                def field_fn(self) -> List[m]:
                    return []
                return field_fn
            setattr(API, f"get_model_{i}", field(make_field(model)))

        start_time = time.perf_counter()
        api = GraphQLAPI(root_type=API)
        schema, _ = api.build()
        end_time = time.perf_counter()

        build_time = (end_time - start_time) * 1000
        print(f"\n50-type wide schema build time: {build_time:.2f}ms")

        from graphql import print_schema
        schema_sdl = print_schema(schema)
        for i in range(50):
            assert f"Model{i}" in schema_sdl

        assert build_time < 2000, f"Schema build took too long: {build_time:.2f}ms"

    def test_event_edge_pattern_like_outeract(self) -> None:
        """Test the Event/Edge pattern from outeract with recursive relationships."""

        class EdgeTypeEnum(str, Enum):
            PARTICIPANT = "participant"
            IN_CONVERSATION = "in_conversation"
            ATTACHMENT = "attachment"
            SENDER = "sender"

        class File(BaseModel):
            id: str
            url: str
            mime_type: str
            size: int

        class Edge(BaseModel):
            id: str
            source_node_id: str
            source_node_type: str
            target_node_id: str
            target_node_type: str
            edge_type: EdgeTypeEnum
            extra_data: Optional[Dict[str, Any]] = None

        class EventSchema(BaseModel):
            id: str
            name: str
            json_schema: Dict[str, Any]

        class Event(BaseModel):
            id: str
            event_type: str
            payload: Dict[str, Any]
            processed_at: Optional[str] = None
            event_schema: Optional[EventSchema] = None
            edges: List[Edge] = []
            attachments: List[File] = []
            origin_event_id: Optional[str] = None

        class User(BaseModel):
            id: str
            name: str
            is_system_user: bool = False
            identities: List[str] = []  # Simplified for test

        class Conversation(BaseModel):
            id: str
            title: Optional[str] = None
            participants: List[User] = []
            messages: List[Event] = []
            created_at: str
            updated_at: str

        class Application(BaseModel):
            id: str
            name: str
            events: List[Event] = []
            users: List[User] = []
            conversations: List[Conversation] = []

        class EventAPI:
            @field
            def applications(self) -> List[Application]:
                return []

            @field
            def events(
                self,
                app_id: str,
                event_type: Optional[str] = None,
                limit: int = 100
            ) -> List[Event]:
                return []

            @field
            def conversations(
                self,
                app_id: str,
                user_id: Optional[str] = None
            ) -> List[Conversation]:
                return []

        start_time = time.perf_counter()
        api = GraphQLAPI(root_type=EventAPI)
        schema, _ = api.build()
        end_time = time.perf_counter()

        build_time = (end_time - start_time) * 1000
        print(f"\nEvent/Edge pattern schema build time: {build_time:.2f}ms")

        from graphql import print_schema
        schema_sdl = print_schema(schema)
        assert "Event" in schema_sdl
        assert "Edge" in schema_sdl
        assert "Conversation" in schema_sdl
        assert "Application" in schema_sdl

        assert build_time < 500, f"Schema build took too long: {build_time:.2f}ms"


class TestQueryExecution:
    """Tests for query execution performance with nested data."""

    def test_deeply_nested_query_execution(self) -> None:
        """Test query execution time with deeply nested data."""

        class PlatformConnection(BaseModel):
            id: str
            platform_name: str

        class UserIdentity(BaseModel):
            id: str
            external_id: str
            platform_connection: Optional[PlatformConnection] = None

        class User(BaseModel):
            id: str
            name: str
            identities: List[UserIdentity] = []

        class Application(BaseModel):
            id: str
            name: str
            users: List[User] = []

        class Organisation(BaseModel):
            id: str
            name: str
            applications: List[Application] = []

        # Create test data with moderate nesting
        def create_test_data():
            orgs = []
            for org_i in range(5):  # 5 orgs
                apps = []
                for app_i in range(3):  # 3 apps per org
                    users = []
                    for user_i in range(10):  # 10 users per app
                        identities = []
                        for id_i in range(2):  # 2 identities per user
                            identity = UserIdentity(
                                id=f"identity-{org_i}-{app_i}-{user_i}-{id_i}",
                                external_id=f"ext-{id_i}",
                                platform_connection=PlatformConnection(
                                    id=f"platform-{id_i}",
                                    platform_name="whatsapp" if id_i == 0 else "email"
                                )
                            )
                            identities.append(identity)
                        user = User(
                            id=f"user-{org_i}-{app_i}-{user_i}",
                            name=f"User {user_i}",
                            identities=identities
                        )
                        users.append(user)
                    app = Application(
                        id=f"app-{org_i}-{app_i}",
                        name=f"App {app_i}",
                        users=users
                    )
                    apps.append(app)
                org = Organisation(
                    id=f"org-{org_i}",
                    name=f"Organisation {org_i}",
                    applications=apps
                )
                orgs.append(org)
            return orgs

        test_data = create_test_data()

        class API:
            @field
            def organisations(self) -> List[Organisation]:
                return test_data

        api = GraphQLAPI(root_type=API)

        # Full nested query
        query = """
            query {
                organisations {
                    id
                    name
                    applications {
                        id
                        name
                        users {
                            id
                            name
                            identities {
                                id
                                externalId
                                platformConnection {
                                    id
                                    platformName
                                }
                            }
                        }
                    }
                }
            }
        """

        # Warm up
        api.execute(query)

        # Measure execution time (average of 5 runs)
        times = []
        for _ in range(5):
            start_time = time.perf_counter()
            result = api.execute(query)
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)
            assert result.errors is None

        avg_time = sum(times) / len(times)
        print(f"\nNested query execution (5 orgs, 3 apps, 10 users, 2 identities each):")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Min: {min(times):.2f}ms, Max: {max(times):.2f}ms")

        # Should execute in under 200ms
        assert avg_time < 200, f"Query execution too slow: {avg_time:.2f}ms"

    def test_recursive_self_referencing_model(self) -> None:
        """Test performance with self-referencing models (like employee hierarchy)."""

        class Employee(BaseModel):
            id: str
            name: str
            title: str
            direct_reports: List["Employee"] = []

        Employee.model_rebuild()

        # Create a hierarchy: CEO -> 3 VPs -> 3 Directors each -> 3 Managers each
        def create_hierarchy(prefix: str, levels: int, breadth: int, max_levels: int) -> Employee:
            if levels == 0:
                return Employee(id=f"{prefix}", name=f"Employee {prefix}", title="Individual Contributor")

            reports = []
            for i in range(breadth):
                child = create_hierarchy(f"{prefix}-{i}", levels - 1, breadth, max_levels)
                reports.append(child)

            titles = ["IC", "Manager", "Director", "VP", "CEO"]
            return Employee(
                id=prefix,
                name=f"Employee {prefix}",
                title=titles[min(levels, 4)],
                direct_reports=reports
            )

        # Create 4-level hierarchy with 3 reports at each level = 1 + 3 + 9 + 27 = 40 employees
        ceo = create_hierarchy("ceo", 4, 3, 4)

        class OrgAPI:
            @field
            def org_chart(self) -> Employee:
                return ceo

        api = GraphQLAPI(root_type=OrgAPI)

        query = """
            query {
                orgChart {
                    id
                    name
                    title
                    directReports {
                        id
                        name
                        title
                        directReports {
                            id
                            name
                            title
                            directReports {
                                id
                                name
                                title
                                directReports {
                                    id
                                    name
                                    title
                                }
                            }
                        }
                    }
                }
            }
        """

        start_time = time.perf_counter()
        result = api.execute(query)
        end_time = time.perf_counter()

        exec_time = (end_time - start_time) * 1000
        print(f"\nRecursive hierarchy query (121 employees, 5 levels): {exec_time:.2f}ms")

        assert result.errors is None, f"Query errors: {result.errors}"
        assert result.data["orgChart"]["title"] == "CEO"
        assert len(result.data["orgChart"]["directReports"]) == 3

        assert exec_time < 100, f"Recursive query too slow: {exec_time:.2f}ms"


class TestMemoryUsage:
    """Tests for memory usage with large schemas."""

    def test_schema_memory_usage(self) -> None:
        """Test memory usage during schema building with many types."""

        # Create many interconnected types
        class BaseEntity(BaseModel):
            id: str
            created_at: str
            updated_at: str

        class Tag(BaseEntity):
            name: str
            color: str

        class Category(BaseEntity):
            name: str
            description: Optional[str] = None
            tags: List[Tag] = []

        class Author(BaseEntity):
            name: str
            email: str
            bio: Optional[str] = None

        class Comment(BaseEntity):
            content: str
            author: Author
            replies: List["Comment"] = []

        Comment.model_rebuild()

        class Article(BaseEntity):
            title: str
            content: str
            author: Author
            category: Optional[Category] = None
            tags: List[Tag] = []
            comments: List[Comment] = []

        class API:
            @field
            def articles(self) -> List[Article]:
                return []

            @field
            def authors(self) -> List[Author]:
                return []

            @field
            def categories(self) -> List[Category]:
                return []

            @field
            def tags(self) -> List[Tag]:
                return []

        # Measure memory usage
        tracemalloc.start()

        api = GraphQLAPI(root_type=API)
        schema, _ = api.build()

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\nSchema memory usage:")
        print(f"  Current: {current / 1024:.2f} KB")
        print(f"  Peak: {peak / 1024:.2f} KB")

        # Memory should stay under 10MB for this moderate schema
        assert peak < 10 * 1024 * 1024, f"Peak memory too high: {peak / 1024 / 1024:.2f} MB"


class TestSchemaRebuilding:
    """Tests for schema caching and rebuilding performance."""

    def test_repeated_schema_builds(self) -> None:
        """Test that repeated schema builds don't degrade in performance."""

        class SimpleModel(BaseModel):
            id: str
            name: str

        class API:
            @field
            def items(self) -> List[SimpleModel]:
                return []

        times = []
        for i in range(10):
            start_time = time.perf_counter()
            api = GraphQLAPI(root_type=API)
            schema, _ = api.build()
            end_time = time.perf_counter()
            times.append((end_time - start_time) * 1000)

        print(f"\n10 repeated schema builds:")
        print(f"  Times: {[f'{t:.2f}' for t in times]}")
        print(f"  Average: {sum(times)/len(times):.2f}ms")

        # Later builds should not be significantly slower than first
        # Allow 50% variance
        first_build = times[0]
        last_build = times[-1]
        assert last_build < first_build * 1.5, \
            f"Performance degradation: first={first_build:.2f}ms, last={last_build:.2f}ms"


class TestDataclassNesting:
    """Tests specifically for dataclass-based nested types."""

    def test_deeply_nested_dataclasses(self) -> None:
        """Test schema building with deeply nested dataclasses."""

        @dataclass
        class Address:
            street: str
            city: str
            country: str
            postal_code: Optional[str] = None

        @dataclass
        class ContactInfo:
            email: str
            phone: Optional[str] = None
            address: Optional[Address] = None

        @dataclass
        class Department:
            id: str
            name: str
            budget: int

        @dataclass
        class Employee:
            id: str
            name: str
            contact: ContactInfo
            department: Department

        @dataclass
        class Company:
            id: str
            name: str
            headquarters: Address
            ceo: Optional[Employee] = None

        class API:
            @field
            def companies(self) -> List[Company]:
                return []

            @field
            def company(self, company_id: str) -> Optional[Company]:
                return None

        start_time = time.perf_counter()
        api = GraphQLAPI(root_type=API)
        schema, _ = api.build()
        end_time = time.perf_counter()

        build_time = (end_time - start_time) * 1000
        print(f"\nDataclass nested schema build time: {build_time:.2f}ms")

        from graphql import print_schema
        schema_sdl = print_schema(schema)
        assert "Company" in schema_sdl
        assert "Employee" in schema_sdl
        assert "Department" in schema_sdl
        assert "ContactInfo" in schema_sdl
        assert "Address" in schema_sdl

        assert build_time < 500, f"Schema build took too long: {build_time:.2f}ms"


class TestInputTypePerformance:
    """Tests for input type performance with nested inputs."""

    def test_nested_input_types(self) -> None:
        """Test schema building and execution with nested input types."""

        class AddressInput(BaseModel):
            street: str
            city: str
            country: str

        class ContactInput(BaseModel):
            email: str
            phone: Optional[str] = None
            address: AddressInput

        class PersonInput(BaseModel):
            name: str
            age: int
            contact: ContactInput
            tags: List[str] = []

        class Person(BaseModel):
            id: str
            name: str
            age: int
            contact: ContactInput

        class API:
            @field(mutable=True)
            def create_person(self, person: PersonInput) -> Person:
                return Person(
                    id="generated-id",
                    name=person.name,
                    age=person.age,
                    contact=person.contact
                )

        start_time = time.perf_counter()
        api = GraphQLAPI(root_type=API)
        schema, _ = api.build()
        end_time = time.perf_counter()

        build_time = (end_time - start_time) * 1000
        print(f"\nNested input types schema build time: {build_time:.2f}ms")

        # Test mutation execution
        mutation = """
            mutation {
                createPerson(person: {
                    name: "Test User",
                    age: 30,
                    contact: {
                        email: "test@example.com",
                        address: {
                            street: "123 Main St",
                            city: "Test City",
                            country: "Test Country"
                        }
                    },
                    tags: ["developer", "tester"]
                }) {
                    id
                    name
                    age
                    contact {
                        email
                        address {
                            city
                        }
                    }
                }
            }
        """

        exec_start = time.perf_counter()
        result = api.execute(mutation)
        exec_end = time.perf_counter()

        exec_time = (exec_end - exec_start) * 1000
        print(f"Nested input mutation execution time: {exec_time:.2f}ms")

        assert result.errors is None
        assert result.data["createPerson"]["name"] == "Test User"

        assert build_time < 500, f"Schema build took too long: {build_time:.2f}ms"
        assert exec_time < 100, f"Mutation execution too slow: {exec_time:.2f}ms"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
