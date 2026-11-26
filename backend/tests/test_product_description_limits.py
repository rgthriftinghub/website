import pytest
from pydantic import ValidationError

from app.schemas.catalog import ProductCreate, ProductUpdate


def test_product_description_fields_accept_50000_characters_and_sanitize() -> None:
    long_text = "x" * 50000
    product = ProductUpdate(
        description=f" <b>{long_text}</b> ",
        short_description=f" <b>{long_text}</b> ",
        meta_description=f" <b>{long_text}</b> ",
    )

    assert product.description == long_text
    assert product.short_description == long_text
    assert product.meta_description == long_text


def test_product_create_accepts_2000_characters_in_all_description_fields() -> None:
    long_text = "x" * 2000
    product = ProductCreate(
        name="Vintage denim jacket",
        slug="vintage-denim-jacket",
        sku="RG-DENIM-001",
        short_description=long_text,
        description=long_text,
        meta_description=long_text,
        category_id="00000000-0000-0000-0000-000000000001",
        regular_price="4500.00",
        condition="GOOD",
        gender="MEN",
        product_type="JACKET",
    )

    assert len(product.short_description or "") == 2000
    assert len(product.description or "") == 2000
    assert len(product.meta_description or "") == 2000


def test_product_update_accepts_2000_characters_in_all_description_fields() -> None:
    long_text = "x" * 2000
    product = ProductUpdate(
        short_description=long_text,
        description=long_text,
        meta_description=long_text,
    )

    assert len(product.short_description or "") == 2000
    assert len(product.description or "") == 2000
    assert len(product.meta_description or "") == 2000


@pytest.mark.parametrize("field", ["description", "short_description", "meta_description"])
def test_product_description_fields_reject_more_than_50000_characters(field: str) -> None:
    with pytest.raises(ValidationError):
        ProductUpdate(**{field: "x" * 50001})


def test_product_update_reports_the_exact_field_for_text_over_50000() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ProductUpdate(description="x" * 50001)

    error = exc_info.value.errors()[0]
    assert error["loc"] == ("description",)
    assert error["msg"] == "String should have at most 50000 characters"
