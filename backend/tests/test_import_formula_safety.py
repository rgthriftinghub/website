from app.services.imports import parse_file


def test_csv_import_neutralizes_formula_prefixes_in_text_fields():
    content = (
        b"SKU,Product Name,Description,Regular Price,Stock\n"
        b"=1+1,+cmd,@SUM(A1),12.50,3\n"
    )

    fields, rows = parse_file("products.csv", content)

    assert {"sku", "name", "description", "regular_price", "stock"} <= set(fields)
    assert rows[0]["sku"].startswith("'=")
    assert rows[0]["name"].startswith("'+")
    assert rows[0]["description"].startswith("'@")
    assert rows[0]["regular_price"] == "12.50"
    assert rows[0]["stock"] == "3"


def test_excel_import_neutralizes_formula_prefixes_in_text_fields():
    from io import BytesIO
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["SKU", "Product Name", "Regular Price"])
    sheet.append(["@cmd", "=1+1", 10])
    buffer = BytesIO()
    workbook.save(buffer)

    fields, rows = parse_file("products.xlsx", buffer.getvalue())

    assert {"sku", "name", "regular_price"} <= set(fields)
    assert rows[0]["sku"].startswith("'@")
    assert rows[0]["name"].startswith("'=")
    assert rows[0]["regular_price"] == 10
