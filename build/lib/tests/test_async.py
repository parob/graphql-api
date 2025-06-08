import asyncio

from graphql_api.api import GraphQLAPI


class TestAsync:
    def test_basic_async(self):
        api = GraphQLAPI()

        @api.type
        class Math:
            @api.field
            async def test_square(self, number: int) -> int:
                await asyncio.sleep(0.1)
                return number * number

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math(self) -> Math:
                return Math()

            @api.field
            async def async_math(self) -> Math:
                math = Math()
                precalculated = await math.test_square(5)
                assert precalculated == 25
                return Math()

        result_1 = api.execute(
            """
            query GetTestSquare {
                math {
                    square: testSquare(number: 5)
                }
            }
            """
        )
        assert not result_1.errors
        assert result_1.data == {"math": {"square": 25}}

        result_2 = api.execute(
            """
            query GetTestSquare {
                asyncMath {
                    square: testSquare(number: 5)
                }
            }
            """
        )
        assert not result_2.errors
        assert result_2.data == {"asyncMath": {"square": 25}}
