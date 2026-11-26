"""Product import from CSV or Excel.

**Uploaded rows are never written straight to the catalogue.** The flow is:

    upload -> parse -> validate -> ImportBatch (VALIDATED) -> admin confirms -> commit

The parsed rows and their per-row verdicts are stored on the batch, so the preview
an admin approves is exactly what gets applied — the file is not re-parsed and
cannot change in between.

Rows are classified per row, not per file: a file with three bad rows still imports
the other ninety-seven. Errors block a row; warnings do not.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezones import utc_now
from app.models.admin import ImportBatch
from app.models.brand import Brand
from app.models.category import Category, Subcategory
from app.models.enums import Gender, ImportStatus, ProductCondition, ProductType, parse_product_condition
from app.models.inventory import InventoryItem
from app.models.product import Product
from app.models.user import User
from app.models.variant import ProductVariant
from app.services import activity
from app.services.exceptions import InvalidRequestError, NotFoundError

MAX_IMPORT_ROWS = 2_000

# Column name -> canonical field. Matching is case-insensitive and ignores spaces
# and underscores, so "Product Name", "product_name", and "productname" all work.
COLUMN_ALIASES: dict[str, str] = {
    "sku": "sku",
    "variantsku": "sku",
    "itemcode": "item_code",
    "singlepiece": "single_piece",
    "productname": "name",
    "name": "name",
    "product": "name",
    "brand": "brand",
    "category": "category",
    "subcategory": "subcategory",
    "variant": "variant_name",
    "size": "size",
    "waist": "waist",
    "colour": "color",
    "color": "color",
    "fabric": "fabric",
    "condition": "condition",
    "gender": "gender",
    "producttype": "product_type",
    "type": "product_type",
    "price": "regular_price",
    "regularprice": "regular_price",
    "saleprice": "sale_price",
    "stock": "stock",
    "quantity": "stock",
    "lowstockthreshold": "low_stock_threshold",
    "threshold": "low_stock_threshold",
    "featured": "is_featured",
    "newarrival": "is_new_arrival",
    "status": "status",
    "shortdescription": "short_description",
    "description": "description",
}

REQUIRED_FIELDS = ("sku", "name", "category", "regular_price")
TEXT_FIELDS = {
    "sku", "item_code", "name", "brand", "category", "subcategory", "variant_name",
    "size", "color", "fabric", "condition", "gender", "product_type",
    "short_description", "description", "status",
}

TEMPLATE_COLUMNS = [
    "SKU", "Item Code", "Single Piece", "Product Name", "Brand", "Category", "Subcategory", "Size", "Waist",
    "Colour", "Fabric", "Condition", "Gender", "Product Type",
    "Regular Price", "Sale Price", "Stock", "Low Stock Threshold",
    "Featured", "New Arrival", "Status",
]


@dataclass(slots=True)
class RowVerdict:
    row_number: int
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    action: str = "create"  # create | update | skip

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def as_json(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "data": {key: str(value) if value is not None else None for key, value in self.data.items()},
            "errors": self.errors,
            "warnings": self.warnings,
            "action": self.action,
        }


def _normalise_header(value: Any) -> str | None:
    if value is None:
        return None
    key = "".join(str(value).lower().split()).replace("_", "").replace("-", "")
    return COLUMN_ALIASES.get(key)


def _sanitize_import_value(value: Any) -> Any:
    """Neutralize spreadsheet formula prefixes in imported text cells."""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if stripped.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _parse_decimal(raw: Any) -> Decimal | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"'{raw}' is not a valid number")


def _parse_int(raw: Any) -> int | None:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(float(str(raw).replace(",", "").strip()))
    except (TypeError, ValueError):
        raise ValueError(f"'{raw}' is not a whole number")


def _parse_bool(raw: Any) -> bool | None:
    if raw is None or str(raw).strip() == "":
        return None
    return str(raw).strip().lower() in ("yes", "true", "1", "y")


def parse_file(filename: str, content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    """Read a CSV or Excel upload into header fields plus raw row dicts."""
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xlsm")):
        rows = _parse_excel(content)
    elif lower.endswith(".csv"):
        rows = _parse_csv(content)
    else:
        raise InvalidRequestError("Upload a .csv or .xlsx file")

    if not rows:
        raise InvalidRequestError("The file has no data rows")
    if len(rows) > MAX_IMPORT_ROWS:
        raise InvalidRequestError(
            f"That file has {len(rows):,} rows. Please split it into files of at most "
            f"{MAX_IMPORT_ROWS:,} rows."
        )

    fields = sorted({key for row in rows for key in row})
    return fields, rows


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    # utf-8-sig strips the BOM Excel writes, which would otherwise corrupt the
    # first column name and make "SKU" unrecognisable.
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    try:
        raw_header = next(reader)
    except StopIteration:
        return []

    mapping = {index: _normalise_header(name) for index, name in enumerate(raw_header)}
    if not any(mapping.values()):
        raise InvalidRequestError(
            "No recognisable columns found. Download the template to see the expected headers."
        )

    rows: list[dict[str, Any]] = []
    for values in reader:
        if not any(str(value).strip() for value in values):
            continue
        row: dict[str, Any] = {}
        for index, value in enumerate(values):
            field_name = mapping.get(index)
            if field_name:
                row[field_name] = _sanitize_import_value(value) if field_name in TEXT_FIELDS else value
        rows.append(row)
    return rows


def _parse_excel(content: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    iterator = sheet.iter_rows(values_only=True)
    try:
        raw_header = next(iterator)
    except StopIteration:
        return []

    mapping = {index: _normalise_header(name) for index, name in enumerate(raw_header)}
    if not any(mapping.values()):
        raise InvalidRequestError(
            "No recognisable columns found. Download the template to see the expected headers."
        )

    rows: list[dict[str, Any]] = []
    for values in iterator:
        if values is None or not any(value is not None and str(value).strip() for value in values):
            continue
        row: dict[str, Any] = {}
        for index, value in enumerate(values):
            field_name = mapping.get(index)
            if field_name:
                row[field_name] = _sanitize_import_value(value) if field_name in TEXT_FIELDS else value
        rows.append(row)
    workbook.close()
    return rows


def validate_rows(db: Session, rows: list[dict[str, Any]]) -> list[RowVerdict]:
    """Check every row against the catalogue without writing anything.

    Duplicate SKUs *within the file* are caught as well as against the database —
    two rows claiming the same SKU would otherwise silently overwrite each other.
    """
    categories = {
        name.lower(): row
        for name, row in (
            (category.name, category)
            for category in db.execute(select(Category)).scalars().all()
        )
    }
    subcategories: dict[tuple[uuid.UUID, str], Subcategory] = {
        (sub.category_id, sub.name.lower()): sub
        for sub in db.execute(select(Subcategory)).scalars().all()
    }
    brands = {
        brand.name.lower(): brand for brand in db.execute(select(Brand)).scalars().all()
    }
    existing_variants = {
        sku.lower()
        for sku in db.execute(select(ProductVariant.sku)).scalars().all()
    }

    seen_skus: set[str] = set()
    verdicts: list[RowVerdict] = []

    for offset, raw in enumerate(rows):
        # +2 because row 1 is the header, so this matches what the admin sees.
        verdict = RowVerdict(row_number=offset + 2, data={})
        data: dict[str, Any] = {}

        for name in REQUIRED_FIELDS:
            if not str(raw.get(name) or "").strip():
                verdict.errors.append(f"{name.replace('_', ' ')} is required")

        sku = str(raw.get("sku") or "").strip()
        if sku:
            data["sku"] = sku
            if sku.lower() in seen_skus:
                verdict.errors.append(f"SKU '{sku}' appears more than once in this file")
            seen_skus.add(sku.lower())
            if sku.lower() in existing_variants:
                verdict.action = "update"
                verdict.warnings.append("Existing SKU — stock and price will be updated")

        data["name"] = str(raw.get("name") or "").strip()
        code = str(raw.get("item_code") or "").strip()
        if code:
            data["item_code"] = code

        category_name = str(raw.get("category") or "").strip()
        category = categories.get(category_name.lower())
        if category_name and category is None:
            verdict.errors.append(f"Category '{category_name}' does not exist")
        elif category is not None:
            data["category_id"] = category.id

        subcategory_name = str(raw.get("subcategory") or "").strip()
        if subcategory_name and category is not None:
            subcategory = subcategories.get((category.id, subcategory_name.lower()))
            if subcategory is None:
                verdict.warnings.append(
                    f"Subcategory '{subcategory_name}' is not under {category.name}; it will be left unset"
                )
            else:
                data["subcategory_id"] = subcategory.id

        brand_name = str(raw.get("brand") or "").strip()
        if brand_name:
            brand = brands.get(brand_name.lower())
            if brand is None:
                verdict.warnings.append(f"Brand '{brand_name}' does not exist; it will be left unset")
            else:
                data["brand_id"] = brand.id

        for field_name, parser in (
            ("regular_price", _parse_decimal),
            ("sale_price", _parse_decimal),
            ("stock", _parse_int),
            ("low_stock_threshold", _parse_int),
            ("waist", _parse_int),
        ):
            try:
                parsed = parser(raw.get(field_name))
                if parsed is not None:
                    data[field_name] = parsed
            except ValueError as exc:
                verdict.errors.append(f"{field_name.replace('_', ' ')}: {exc}")

        if data.get("regular_price") is not None and data["regular_price"] <= 0:
            verdict.errors.append("Regular price must be greater than zero")
        if (
            data.get("sale_price") is not None
            and data.get("regular_price") is not None
            and data["sale_price"] >= data["regular_price"]
        ):
            verdict.warnings.append("Sale price is not below the regular price; it will be ignored")
            data.pop("sale_price", None)
        if data.get("stock") is not None and data["stock"] < 0:
            verdict.errors.append("Stock cannot be negative")

        for field_name, enum_class in (
            ("condition", ProductCondition),
            ("gender", Gender),
            ("product_type", ProductType),
        ):
            raw_value = str(raw.get(field_name) or "").strip()
            if not raw_value:
                continue
            candidate = raw_value.upper().replace(" ", "_").replace("-", "_")
            try:
                data[field_name] = (
                    parse_product_condition(candidate)
                    if enum_class is ProductCondition
                    else enum_class(candidate)
                )
            except ValueError:
                allowed = ", ".join(item.value for item in enum_class)
                verdict.errors.append(f"{field_name.replace('_', ' ')} '{raw_value}' is not one of: {allowed}")

        for field_name in ("size", "color", "fabric", "variant_name", "short_description", "description"):
            value = str(raw.get(field_name) or "").strip()
            if value:
                data[field_name] = value

        for field_name in ("is_featured", "is_new_arrival"):
            parsed_bool = _parse_bool(raw.get(field_name))
            if parsed_bool is not None:
                data[field_name] = parsed_bool

        parsed_single_piece = _parse_bool(raw.get("single_piece"))
        if parsed_single_piece is not None:
            data["single_piece"] = parsed_single_piece
            if parsed_single_piece and data.get("stock", 0) > 1:
                verdict.errors.append("Single-piece stock cannot exceed one unit")

        status = str(raw.get("status") or "").strip().lower()
        if status:
            data["is_active"] = status not in ("inactive", "no", "false", "0", "disabled")

        if data.get("size") is None and data.get("waist") is None:
            verdict.warnings.append("No size or waist given; a single default variant will be used")

        verdict.data = data
        verdicts.append(verdict)

    return verdicts


def create_batch(
    db: Session, filename: str, content: bytes, *, actor: User
) -> ImportBatch:
    """Parse, validate, and store an upload for review. Nothing is imported yet."""
    _, rows = parse_file(filename, content)
    verdicts = validate_rows(db, rows)

    valid = sum(1 for verdict in verdicts if verdict.is_valid)
    warnings = sum(1 for verdict in verdicts if verdict.is_valid and verdict.warnings)
    errors = len(verdicts) - valid

    batch = ImportBatch(
        filename=filename[:255],
        status=ImportStatus.VALIDATED if valid else ImportStatus.FAILED,
        total_rows=len(verdicts),
        valid_rows=valid,
        warning_rows=warnings,
        error_rows=errors,
        rows_json=[verdict.as_json() for verdict in verdicts],
        error_summary=(
            None if valid else "No row passed validation; nothing can be imported."
        ),
        uploaded_by_user_id=actor.id,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: uuid.UUID) -> ImportBatch:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise NotFoundError("Import batch not found")
    return batch


def _slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "product"


def _unique_slug(db: Session, base: str) -> str:
    slug = _slugify(base)
    candidate = slug
    suffix = 2
    while db.execute(select(Product.id).where(Product.slug == candidate)).first():
        candidate = f"{slug}-{suffix}"
        suffix += 1
    return candidate


def commit_batch(db: Session, batch_id: uuid.UUID, *, actor: User) -> ImportBatch:
    """Apply the validated rows.

    Only rows that passed validation are applied; error rows are skipped and remain
    visible in the batch. The whole apply runs in one transaction, so a failure
    part-way leaves the catalogue untouched rather than half-imported.
    """
    batch = get_batch(db, batch_id)
    if batch.status is ImportStatus.COMMITTED:
        raise InvalidRequestError("This batch has already been imported")
    if not batch.is_committable:
        raise InvalidRequestError("This batch has no valid rows to import")

    created = 0
    updated = 0

    for entry in batch.rows_json or []:
        if entry.get("errors"):
            continue
        data = entry.get("data") or {}
        sku = (data.get("sku") or "").strip()
        if not sku:
            continue

        variant = db.execute(
            select(ProductVariant).where(func.lower(ProductVariant.sku) == sku.lower())
        ).scalar_one_or_none()

        regular_price = Decimal(data["regular_price"]) if data.get("regular_price") else None
        sale_price = Decimal(data["sale_price"]) if data.get("sale_price") else None
        stock = int(data["stock"]) if data.get("stock") is not None else 0
        threshold = int(data["low_stock_threshold"]) if data.get("low_stock_threshold") else 3
        waist = int(data["waist"]) if data.get("waist") is not None else None

        if variant is not None:
            # Existing SKU: refresh price and stock, leave identity alone.
            product = variant.product
            if regular_price is not None:
                product.regular_price = regular_price
            product.sale_price = sale_price
            if data.get("item_code"):
                product.item_code = data["item_code"]
            if data.get("single_piece") is not None:
                product.single_piece = data["single_piece"]
            if variant.inventory is None:
                variant.inventory = InventoryItem(quantity=stock, low_stock_threshold=threshold)
            else:
                variant.inventory.quantity = stock
                variant.inventory.low_stock_threshold = threshold
            updated += 1
            continue

        name = data.get("name") or sku
        product = Product(
            name=name,
            slug=_unique_slug(db, name),
            sku=sku,
            item_code=data.get("item_code") or None,
            single_piece=bool(data.get("single_piece", False)),
            category_id=uuid.UUID(data["category_id"]),
            subcategory_id=uuid.UUID(data["subcategory_id"]) if data.get("subcategory_id") else None,
            brand_id=uuid.UUID(data["brand_id"]) if data.get("brand_id") else None,
            regular_price=regular_price or Decimal("0.01"),
            sale_price=sale_price,
            condition=ProductCondition(data.get("condition", "GOOD")),
            gender=Gender(data.get("gender", "UNISEX")),
            product_type=ProductType(data.get("product_type", "SHIRT")),
            color=data.get("color"),
            fabric=data.get("fabric"),
            short_description=data.get("short_description"),
            description=data.get("description"),
            is_featured=str(data.get("is_featured", "")).lower() == "true",
            is_new_arrival=str(data.get("is_new_arrival", "")).lower() == "true",
            is_active=str(data.get("is_active", "True")).lower() != "false",
        )
        variant = ProductVariant(
            sku=sku,
            size=data.get("size"),
            waist=waist,
            color=data.get("color"),
            variant_name=data.get("variant_name"),
            is_active=True,
        )
        variant.inventory = InventoryItem(quantity=stock, low_stock_threshold=threshold)
        product.variants.append(variant)
        db.add(product)
        created += 1

    batch.status = ImportStatus.COMMITTED
    batch.created_count = created
    batch.updated_count = updated
    batch.committed_at = utc_now()

    activity.log(
        db,
        actor=actor,
        action=activity.IMPORT_COMMITTED,
        entity_type="ImportBatch",
        entity_id=batch.id,
        description=f"Imported {batch.filename}: {created} created, {updated} updated",
        metadata={"created": created, "updated": updated, "skipped": batch.error_rows},
        commit=False,
    )
    db.commit()
    db.refresh(batch)
    return batch


def cancel_batch(db: Session, batch_id: uuid.UUID) -> ImportBatch:
    batch = get_batch(db, batch_id)
    if batch.status is ImportStatus.COMMITTED:
        raise InvalidRequestError("This batch has already been imported")
    batch.status = ImportStatus.CANCELLED
    db.commit()
    db.refresh(batch)
    return batch


def error_report_rows(batch: ImportBatch) -> tuple[list[str], list[list[Any]]]:
    """Downloadable report of the rows that could not be imported."""
    header = ["Row", "SKU", "Product", "Severity", "Messages"]
    rows: list[list[Any]] = []
    for entry in batch.rows_json or []:
        errors = entry.get("errors") or []
        warnings = entry.get("warnings") or []
        if not errors and not warnings:
            continue
        data = entry.get("data") or {}
        rows.append(
            [
                entry.get("row_number"),
                data.get("sku") or "",
                data.get("name") or "",
                "Error" if errors else "Warning",
                "; ".join(errors or warnings),
            ]
        )
    return header, rows
