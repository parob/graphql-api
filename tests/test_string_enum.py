"""Test string enum support"""

import enum
from graphql_api import GraphQLAPI, field


class TestStringEnum:
    def test_string_enum_basic(self):
        """Test basic string enum functionality"""
        
        class Timeframe(str, enum.Enum):
            """A timeframe."""
            LAST_30_DAYS = "last_30_days"
            ALL_TIME = "all_time"
        
        class TestAPI:
            @field
            def get_timeframe(self) -> Timeframe:
                return Timeframe.LAST_30_DAYS
        
        api = GraphQLAPI(root_type=TestAPI)
        
        query = """
            query {
                getTimeframe
            }
        """
        
        result = api.execute(query)
        assert result.data == {'getTimeframe': 'LAST_30_DAYS'}
        assert result.errors is None
    
    def test_string_enum_input(self):
        """Test string enum as input argument"""
        
        class Status(str, enum.Enum):
            PENDING = "pending"
            COMPLETED = "completed"
            FAILED = "failed"
        
        class TestAPI:
            @field
            def echo_status(self, status: Status) -> Status:
                return status
        
        api = GraphQLAPI(root_type=TestAPI)
        
        query = """
            query {
                echoStatus(status: COMPLETED)
            }
        """
        
        result = api.execute(query)
        assert result.data == {'echoStatus': 'COMPLETED'}
        assert result.errors is None
    
    def test_string_enum_with_regular_enum(self):
        """Test that both string enums and regular enums work together"""
        
        class StringStatus(str, enum.Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"
        
        class RegularPriority(enum.Enum):
            LOW = 1
            MEDIUM = 2
            HIGH = 3
        
        class TestAPI:
            @field
            def get_status(self) -> StringStatus:
                return StringStatus.ACTIVE
            
            @field
            def get_priority(self) -> RegularPriority:
                return RegularPriority.HIGH
            
            @field
            def combine(self, status: StringStatus, priority: RegularPriority) -> str:
                return f"{status.value}:{priority.value}"
        
        api = GraphQLAPI(root_type=TestAPI)
        
        # Test query
        query = """
            query {
                getStatus
                getPriority
                combine(status: ACTIVE, priority: HIGH)
            }
        """
        
        result = api.execute(query)
        assert result.data == {
            'getStatus': 'ACTIVE',
            'getPriority': 'HIGH',
            'combine': 'active:3'
        }
        assert result.errors is None
    
    def test_string_enum_optional(self):
        """Test optional string enum"""
        
        from typing import Optional
        
        class Color(str, enum.Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"
        
        class TestAPI:
            @field
            def get_color(self, color: Optional[Color] = None) -> str:
                if color:
                    return f"Color is {color.value}"
                return "No color specified"
        
        api = GraphQLAPI(root_type=TestAPI)
        
        # Test with value
        query1 = """
            query {
                getColor(color: RED)
            }
        """
        result1 = api.execute(query1)
        assert result1.data == {'getColor': 'Color is red'}
        
        # Test without value
        query2 = """
            query {
                getColor
            }
        """
        result2 = api.execute(query2)
        assert result2.data == {'getColor': 'No color specified'}
    
    def test_string_enum_list(self):
        """Test list of string enums"""
        
        from typing import List
        
        class Tag(str, enum.Enum):
            PYTHON = "python"
            JAVASCRIPT = "javascript"
            RUST = "rust"
            GO = "go"
        
        class TestAPI:
            @field
            def get_tags(self) -> List[Tag]:
                return [Tag.PYTHON, Tag.RUST]
            
            @field
            def filter_tags(self, tags: List[Tag]) -> List[Tag]:
                # Return only tags that start with 'P' or 'R'
                return [t for t in tags if t.value[0] in ('p', 'r')]
        
        api = GraphQLAPI(root_type=TestAPI)
        
        # Test returning list
        query1 = """
            query {
                getTags
            }
        """
        result1 = api.execute(query1)
        assert result1.data == {'getTags': ['PYTHON', 'RUST']}
        
        # Test list as input
        query2 = """
            query {
                filterTags(tags: [PYTHON, JAVASCRIPT, RUST, GO])
            }
        """
        result2 = api.execute(query2)
        assert result2.data == {'filterTags': ['PYTHON', 'RUST']}