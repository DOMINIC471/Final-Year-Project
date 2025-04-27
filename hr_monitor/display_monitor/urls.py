from django.urls import path
from .views import (
    HeartRateAPIView,
    display_index,
    manager_index,
    manager_status  # ← make sure this is here
)

urlpatterns = [
    path('', display_index, name='display_index'),
    path('heart_rate/', HeartRateAPIView, name='heart_rate_api'),
    path('manager/', manager_index, name='manager_index'),
    path('manager/status/', manager_status, name='manager_status'),  # ← this line
]
