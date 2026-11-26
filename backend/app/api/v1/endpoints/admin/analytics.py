"""Aggregated operational, sales, product, inventory, and customer analytics."""
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.api.v1.dependencies import require_permission
from app.models.enums import Permission
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.admin_ops import DateRangeParams, SalesAnalyticsQuery, ProductAnalyticsQuery, InventoryAlertQuery
from app.schemas.common import Page
from app.services import analytics as service

router=APIRouter(dependencies=[Depends(require_permission(Permission.REPORTS_VIEW))])

def _window(query): return service.resolve_range(query.preset,date_from=query.date_from,date_to=query.date_to)

@router.get("/dashboard")
def dashboard(query:Annotated[DateRangeParams,Query()],db:Session=Depends(get_db)):
    return service.dashboard_summary(db,_window(query))

@router.get("/sales")
def sales(query:Annotated[SalesAnalyticsQuery,Query()],db:Session=Depends(get_db)):
    window=_window(query); totals=service.sales_totals(db,window)
    return {"range":{"start":window.start,"end":window.end,"label":window.label},"totals":{k:getattr(totals,k) for k in ("gross_sales","discounts","shipping_revenue","net_sales","order_count","items_sold","average_order_value")},"timeseries":service.sales_timeseries(db,window,query.granularity),"by_category":service.sales_by_category(db,window),"by_subcategory":service.sales_by_subcategory(db,window),"by_brand":service.sales_by_brand(db,window,sort=query.brand_sort)}

@router.get("/products")
def products(query:Annotated[ProductAnalyticsQuery,Query()],db:Session=Depends(get_db)):
    rows,total=service.product_performance(db,_window(query),sort=query.sort,limit=query.page_size,offset=(query.page-1)*query.page_size)
    return Page.build(items=rows,page=query.page,page_size=query.page_size,total=total)

@router.get("/inventory")
def inventory(db:Session=Depends(get_db)):
    result=service.inventory_summary(db)
    return {k:getattr(result,k) for k in ("active_products","total_variants","total_units","low_stock_variants","out_of_stock_variants","inventory_value")}

@router.get("/inventory/alerts")
def inventory_alerts(query:Annotated[InventoryAlertQuery,Query()],db:Session=Depends(get_db)):
    rows,total=service.stock_alert_rows(db,out_of_stock=query.out_of_stock,page=query.page,page_size=query.page_size)
    return Page.build(items=rows,page=query.page,page_size=query.page_size,total=total)

@router.get("/customers")
def customers(query:Annotated[DateRangeParams,Query()],db:Session=Depends(get_db)):
    result=service.customer_summary(db,_window(query))
    return {"total":result.total_customers,"new":result.new_customers,"repeat":result.repeat_customers,"loyal":result.loyal_customers,"with_orders":result.customers_with_orders,"average_order_value":result.average_order_value,"total_revenue":result.total_customer_revenue,"segments":{"new":max(0,result.total_customers-result.repeat_customers-result.loyal_customers),"repeat":result.repeat_customers,"loyal":result.loyal_customers}}

@router.get("/orders")
def orders(query:Annotated[DateRangeParams,Query()],db:Session=Depends(get_db)):
    window=_window(query); statuses=service.order_status_counts(db,window); payments=service.payment_status_counts(db,window); methods=service.payment_method_counts(db,window)
    return {"range":{"start":window.start,"end":window.end,"label":window.label},"order_statuses":statuses,"payment_statuses":payments,"payment_methods":methods,"total_orders":sum(statuses.values())}
