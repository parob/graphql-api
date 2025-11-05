import enum

from graphql import print_schema

from graphql_api.api import GraphQLAPI


class TestCustomSuffixes:
    """Tests for custom enum, interface, and input type suffix configuration."""

    def test_default_enum_suffix(self) -> None:
        """Test that enum types default to 'Enum' suffix."""
        api = GraphQLAPI()

        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def animal(self) -> AnimalType:
                return AnimalType.dog

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "AnimalTypeEnum" in schema_sdl
        assert "enum AnimalTypeEnum" in schema_sdl

    def test_custom_enum_suffix(self) -> None:
        """Test that enum_suffix can be customized."""
        api = GraphQLAPI(enum_suffix="Type")

        class Animal(enum.Enum):
            dog = "dog"
            cat = "cat"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def animal(self) -> Animal:
                return Animal.dog

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "AnimalType" in schema_sdl
        assert "enum AnimalType" in schema_sdl
        # Should not have the default suffix
        assert "AnimalEnum" not in schema_sdl

    def test_disabled_enum_suffix(self) -> None:
        """Test that enum_suffix can be disabled with empty string."""
        api = GraphQLAPI(enum_suffix="")

        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def animal(self) -> AnimalType:
                return AnimalType.dog

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "AnimalType" in schema_sdl
        assert "enum AnimalType" in schema_sdl
        # Should not have any suffix
        assert "AnimalTypeEnum" not in schema_sdl

    def test_default_interface_suffix(self) -> None:
        """Test that interface types default to 'Interface' suffix."""
        api = GraphQLAPI()

        @api.type(interface=True)
        class Animal:
            @api.field
            def name(self) -> str:
                ...

        @api.type
        class Dog(Animal):
            @api.field
            def name(self) -> str:
                return "Rex"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def animal(self) -> Animal:
                return Dog()

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "AnimalInterface" in schema_sdl
        assert "interface AnimalInterface" in schema_sdl

    def test_custom_interface_suffix(self) -> None:
        """Test that interface_suffix can be customized."""
        api = GraphQLAPI(interface_suffix="Iface")

        @api.type(interface=True)
        class Animal:
            @api.field
            def name(self) -> str:
                ...

        @api.type
        class Dog(Animal):
            @api.field
            def name(self) -> str:
                return "Rex"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def animal(self) -> Animal:
                return Dog()

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "AnimalIface" in schema_sdl
        assert "interface AnimalIface" in schema_sdl
        # Should not have the default suffix
        assert "AnimalInterface" not in schema_sdl

    def test_disabled_interface_suffix(self) -> None:
        """Test that interface_suffix can be disabled with empty string."""
        api = GraphQLAPI(interface_suffix="")

        @api.type(interface=True)
        class Animal:
            @api.field
            def name(self) -> str:
                ...

        @api.type
        class Dog(Animal):
            @api.field
            def name(self) -> str:
                return "Rex"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def animal(self) -> Animal:
                return Dog()

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "interface Animal {" in schema_sdl
        # Should not have any suffix
        assert "AnimalInterface" not in schema_sdl

    def test_default_input_suffix(self) -> None:
        """Test that input types default to 'Input' suffix."""
        api = GraphQLAPI()

        class PersonInput:
            def __init__(self, name: str):
                self.name = name

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def greet(self, person: PersonInput) -> str:
                return f"Hello {person.name}"

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "PersonInputInput" in schema_sdl
        assert "input PersonInputInput" in schema_sdl

    def test_custom_input_suffix(self) -> None:
        """Test that input_suffix can be customized."""
        api = GraphQLAPI(input_suffix="In")

        class PersonInput:
            def __init__(self, name: str):
                self.name = name

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def greet(self, person: PersonInput) -> str:
                return f"Hello {person.name}"

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "PersonInputIn" in schema_sdl
        assert "input PersonInputIn" in schema_sdl
        # Should not have the default suffix
        assert "PersonInputInput" not in schema_sdl

    def test_disabled_input_suffix(self) -> None:
        """Test that input_suffix can be disabled to prevent double 'Input'."""
        api = GraphQLAPI(input_suffix="")

        class PersonInput:
            def __init__(self, name: str):
                self.name = name

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def greet(self, person: PersonInput) -> str:
                return f"Hello {person.name}"

        schema, _ = api.build()
        schema_sdl = print_schema(schema)
        assert "input PersonInput {" in schema_sdl
        # Should not have double Input
        assert "PersonInputInput" not in schema_sdl

    def test_all_suffixes_custom(self) -> None:
        """Test that all suffixes can be customized simultaneously."""
        api = GraphQLAPI(
            enum_suffix="Kind",
            interface_suffix="Contract",
            input_suffix="Params",
        )

        class Status(enum.Enum):
            active = "active"
            inactive = "inactive"

        @api.type(interface=True)
        class Entity:
            @api.field
            def id(self) -> str:
                ...

        class CreateInput:
            def __init__(self, name: str):
                self.name = name

        @api.type
        class User(Entity):
            @api.field
            def id(self) -> str:
                return "123"

            @api.field
            def name(self) -> str:
                return "Alice"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def user(self, input: CreateInput) -> User:
                return User()

            @api.field
            def status(self) -> Status:
                return Status.active

        schema, _ = api.build()
        schema_sdl = print_schema(schema)

        # Check custom suffixes are applied
        assert "enum StatusKind" in schema_sdl
        assert "interface EntityContract" in schema_sdl
        assert "input CreateInputParams" in schema_sdl

        # Check defaults are NOT applied
        assert "StatusEnum" not in schema_sdl
        assert "EntityInterface" not in schema_sdl
        assert "CreateInputInput" not in schema_sdl

    def test_all_suffixes_disabled(self) -> None:
        """Test that all suffixes can be disabled simultaneously."""
        api = GraphQLAPI(
            enum_suffix="",
            interface_suffix="",
            input_suffix="",
        )

        class Status(enum.Enum):
            active = "active"
            inactive = "inactive"

        @api.type(interface=True)
        class Entity:
            @api.field
            def id(self) -> str:
                ...

        class CreateInput:
            def __init__(self, name: str):
                self.name = name

        @api.type
        class User(Entity):
            @api.field
            def id(self) -> str:
                return "123"

            @api.field
            def name(self) -> str:
                return "Alice"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def user(self, input: CreateInput) -> User:
                return User()

            @api.field
            def status(self) -> Status:
                return Status.active

        schema, _ = api.build()
        schema_sdl = print_schema(schema)

        # Check no suffixes are applied
        assert "enum Status {" in schema_sdl
        assert "interface Entity {" in schema_sdl
        assert "input CreateInput {" in schema_sdl

        # Check defaults are NOT applied
        assert "StatusEnum" not in schema_sdl
        assert "EntityInterface" not in schema_sdl
        assert "CreateInputInput" not in schema_sdl

    def test_mutation_with_custom_suffixes(self) -> None:
        """Test that custom suffixes work with mutations."""
        api = GraphQLAPI(enum_suffix="", input_suffix="")

        class Priority(enum.Enum):
            low = 1
            high = 3

        class TaskInput:
            def __init__(self, priority: Priority):
                self.priority = priority

        @api.type(is_root_type=True)
        class Root:
            @api.field(mutable=True)
            def create_task(self, input: TaskInput) -> str:
                return f"Task created with priority {input.priority.value}"

        schema, _ = api.build()
        schema_sdl = print_schema(schema)

        # Check no suffixes in mutation
        assert "enum Priority {" in schema_sdl
        assert "input TaskInput {" in schema_sdl

        # Verify not the defaults
        assert "PriorityEnum" not in schema_sdl
        assert "TaskInputInput" not in schema_sdl

    def test_suffix_with_mode_2_explicit_types(self) -> None:
        """Test that custom suffixes work with Mode 2 (explicit query/mutation types)."""
        api = GraphQLAPI(
            query_type=None,
            mutation_type=None,
            enum_suffix="Type",
            input_suffix="",
        )

        class Status(enum.Enum):
            active = "active"
            inactive = "inactive"

        class UpdateInput:
            def __init__(self, status: Status):
                self.status = status

        @api.type
        class Query:
            @api.field
            def status(self) -> Status:
                return Status.active

        @api.type
        class Mutation:
            @api.field
            def update(self, input: UpdateInput) -> Status:
                return input.status

        # Manually set types
        api.query_type = Query
        api.mutation_type = Mutation

        schema, _ = api.build()
        schema_sdl = print_schema(schema)

        # Check custom suffix for enum
        assert "enum StatusType {" in schema_sdl
        # Check disabled suffix for input
        assert "input UpdateInput {" in schema_sdl

        # Verify defaults not used
        assert "StatusEnum" not in schema_sdl
        assert "UpdateInputInput" not in schema_sdl
