from typing import Any, Dict, List, Optional

from graphql import DirectiveLocation, GraphQLID

from graphql_api import GraphQLAPI, field, type
from graphql_api.directives import SchemaDirective, deprecated
from graphql_api.federation.directives import (
    composeDirective,
    external,
    inaccessible,
    interfaceObject,
    key,
    link,
    override,
    provides,
    requires,
    shareable,
    tag,
)

dimension = {
    "size": "small",
    "weight": 1,
    "unit": "kg",
}

user = {
    "email": "support@apollographql.com",
    "name": "Jane Smith",
    "total_products_created": 1337,
}

deprecated_product = {
    "sku": "apollo-federation-v1",
    "package": "@apollo/federation-v1",
    "reason": "Migrate to Federation V2",
    "created_by": user,
}

products_research = [
    {
        "study": {
            "case_number": "1234",
            "description": "Federation Study",
        },
        "outcome": None,
    },
    {
        "study": {
            "case_number": "1235",
            "description": "Studio Study",
        },
        "outcome": None,
    },
]

products = [
    {
        "id": "apollo-federation",
        "sku": "federation",
        "package": "@apollo/federation",
        "variation": {"id": "OSS"},
        "dimensions": dimension,
        "research": [products_research[0]],
        "created_by": user,
        "notes": None,
    },
    {
        "id": "apollo-studio",
        "sku": "studio",
        "package": "",
        "variation": {"id": "platform"},
        "dimensions": dimension,
        "research": [products_research[1]],
        "created_by": user,
        "notes": None,
    },
]


custom = SchemaDirective(name="custom", locations=[DirectiveLocation.OBJECT])


@type
class ProductVariation:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @field
    def id(self) -> GraphQLID:
        return self.data["id"]


@type
class CaseStudy:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @field
    def case_number(self) -> GraphQLID:
        return self.data["caseNumber"]

    @field
    def description(self) -> Optional[str]:
        return self.data.get("description")


@key(fields="study { caseNumber }")
@type
class ProductResearch:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @field
    def study(self) -> CaseStudy:
        return CaseStudy(self.data["study"])

    @field
    def outcome(self) -> Optional[str]:
        return self.data.get("outcome")


@shareable
@type
class ProductDimension:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @field
    def size(self) -> Optional[str]:
        return self.data.get("size")

    @field
    def weight(self) -> Optional[float]:
        return self.data.get("weight")

    @inaccessible
    @field
    def unit(self) -> Optional[str]:
        return self.data.get("unit")


@key(fields="email")
@type
class User:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def _resolve_reference(cls, reference: Dict[str, Any]):
        return User(user)

    @requires(fields="totalProductsCreated yearsOfEmployment")
    @field
    def average_products_created_per_year(self) -> Optional[int]:
        total = self.data.get("totalProductsCreated")
        years = self.data.get("yearsOfEmployment")
        if total and years:
            return round(total / years)
        return None

    @external
    @field
    def email(self) -> GraphQLID:
        return self.data.get("email")

    @override(**{"from": "users"})
    @field
    def name(self) -> Optional[str]:
        return self.data.get("name")

    @external
    @field
    def total_products_created(self) -> Optional[int]:
        return self.data.get("totalProductsCreated")

    @external
    @field
    def years_of_employment(self) -> int:
        return self.data.get("yearsOfEmployment", 0)


@key(fields="sku package")
@type
class DeprecatedProduct:
    @classmethod
    def _resolve_reference(cls, reference: Dict[str, Any]):
        return DeprecatedProduct(deprecated_product)

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @field
    def sku(self) -> str:
        return self.data["sku"]

    @field
    def package(self) -> str:
        return self.data["package"]

    @field
    def reason(self) -> Optional[str]:
        return self.data.get("reason")

    @field
    def created_by(self) -> Optional[User]:
        created_by_data = self.data.get("createdBy")
        if created_by_data:
            return User(created_by_data)
        return None


@interfaceObject
@key(fields="id")
@type
class Inventory:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def _resolve_reference(cls, reference: Dict[str, Any]):
        return Inventory(data={"id": reference.get("id")})

    @field
    def id(self) -> GraphQLID:
        return self.data["id"]

    @field
    def deprecated_products(self) -> List[DeprecatedProduct]:
        prods = self.data.get("deprecatedProducts", [])
        return [DeprecatedProduct(p) for p in prods]


@custom
@key(fields="id")
@key(fields="sku package")
@key(fields="sku variation { id }")
@type
class Product:
    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def _resolve_reference(cls, reference: Dict[str, Any]):
        if "id" in reference:
            return Root().product(reference["id"])

        if "sku" in reference and "package" in reference:
            # Check if it matches either known product in the root
            for product_data in products:
                if (
                    product_data.get("sku") == reference["sku"]
                    and product_data.get("package") == reference["package"]
                ):
                    return Product(product_data)

        return None

    @field
    def id(self) -> GraphQLID:
        return self.data["id"]

    @field
    def sku(self) -> Optional[str]:
        return self.data.get("sku")

    @field
    def package(self) -> Optional[str]:
        return self.data.get("package")

    @field
    def variation(self) -> Optional[ProductVariation]:
        variation_data = self.data.get("variation")
        if variation_data:
            return ProductVariation(variation_data)
        return None

    @field
    def dimensions(self) -> Optional[ProductDimension]:
        dims = self.data.get("dimensions")
        if dims:
            return ProductDimension(dims)
        return None

    @provides(fields="totalProductsCreated")
    @field
    def created_by(self) -> Optional[User]:
        user_data = self.data.get("createdBy")
        if user_data:
            return User(user_data)
        return None

    @tag(name="internal")
    @field
    def notes(self) -> Optional[str]:
        return self.data.get("notes")

    @field
    def research(self) -> List[ProductResearch]:
        research_data = self.data.get("research", [])
        return [ProductResearch(r) for r in research_data]


@type
class Root:
    @field
    def product(self, id: GraphQLID) -> Optional[Product]:
        for product_data in products:
            if product_data["id"] == id:
                return Product(product_data)
        return None

    @deprecated(reason="Use product query instead")
    @field
    def deprecated_product(self, sku: str, package: str) -> Optional[DeprecatedProduct]:
        if (
            sku == deprecated_product["sku"]
            and package == deprecated_product["package"]
        ):
            return DeprecatedProduct(deprecated_product)
        return None


def federation_example_api():
    api = GraphQLAPI(root_type=Root, types=[Inventory], federation=True)

    schema, _ = api.build_schema()

    link(
        schema,
        **{
            "url": "https://myspecs.dev/myCustomDirective/v1.0",
            "import": ["@custom"],
        }
    )

    composeDirective(schema, name="@custom")

    return api
