import pytest
from pydantic import ValidationError

from app.schemas.catalog import ProductUpdate


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


@pytest.mark.parametrize("field", ["description", "short_description", "meta_description"])
def test_product_description_fields_reject_more_than_50000_characters(field: str) -> None:
    with pytest.raises(ValidationError):
        ProductUpdate(**{field: "x" * 50001})
