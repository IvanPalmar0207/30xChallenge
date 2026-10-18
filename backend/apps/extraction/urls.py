from django.urls import path

from .views import InvoiceExtractionView

urlpatterns = [
    path(
        "organizations/<uuid:organization_pk>/extraction/",
        InvoiceExtractionView.as_view(),
        name="invoice-extraction",
    ),
]
