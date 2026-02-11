from django.urls import path

from dato_sync import views

app_name = 'dato_sync'
urlpatterns = [
    path("dato-sync/sync/", views.sync, name="dato_sync.sync"),
]