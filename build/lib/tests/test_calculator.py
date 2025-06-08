import enum
from typing import Optional

from graphql_api.api import GraphQLAPI


class Operation(enum.Enum):
    ADD = "ADD"
    SUBTRACT = "SUBTRACT"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"


api = GraphQLAPI()  # Define API instance at module level


@api.type(is_root_type=True)  # Decorate Root class at module level
class Root:
    @api.field
    def calculate(
        self,
        a: float,
        b: float,
        operation: Operation,
    ) -> Optional[float]:
        if operation == Operation.ADD:
            return a + b
        elif operation == Operation.SUBTRACT:
            return a - b
        elif operation == Operation.MULTIPLY:
            return a * b
        elif operation == Operation.DIVIDE:
            if b == 0:
                return None  # Or raise an error
            return a / b
        return None


class TestCalculator:
    def test_calculator_add(self):
        executor = api.executor()  # Use module-level api

        test_query = """
            query TestAdd {
                calculate(a: 10, b: 5, operation: ADD)
            }
        """

        result = executor.execute(test_query)

        expected = {"calculate": 15.0}
        assert not result.errors
        assert result.data == expected

    def test_calculator_subtract(self):
        executor = api.executor()  # Use module-level api

        test_query = """
            query TestSubtract {
                calculate(a: 10, b: 5, operation: SUBTRACT)
            }
        """

        result = executor.execute(test_query)

        expected = {"calculate": 5.0}
        assert not result.errors
        assert result.data == expected

    def test_calculator_multiply(self):
        executor = api.executor()  # Use module-level api

        test_query = """
            query TestMultiply {
                calculate(a: 10, b: 5, operation: MULTIPLY)
            }
        """

        result = executor.execute(test_query)

        expected = {"calculate": 50.0}
        assert not result.errors
        assert result.data == expected

    def test_calculator_divide(self):
        executor = api.executor()  # Use module-level api

        test_query = """
            query TestDivide {
                calculate(a: 10, b: 5, operation: DIVIDE)
            }
        """

        result = executor.execute(test_query)

        expected = {"calculate": 2.0}
        assert not result.errors
        assert result.data == expected

    def test_calculator_divide_by_zero(self):
        executor = api.executor()

        test_query = """
            query TestDivideByZero {
                calculate(a: 10, b: 0, operation: DIVIDE)
            }
        """

        result = executor.execute(test_query)
        expected = {"calculate": None}  # Or handle error appropriately

        assert not result.errors
        assert result.data == expected
