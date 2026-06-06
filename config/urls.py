"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

admin.site.site_header = "Crawler"
admin.site.site_title = "Crawler"
admin.site.index_title = "Crawler Admin"

# Custom model ordering on the admin index (Django sorts alphabetically by
# default). Models not listed fall to the end, keeping alphabetical order.
_MODEL_ORDER = {
    "crawler": ["Crawler", "Domain", "Rule", "Item", "Prop"],
}
_default_get_app_list = admin.AdminSite.get_app_list


def _ordered_get_app_list(self, request, app_label=None):
    app_list = _default_get_app_list(self, request, app_label)
    for app in app_list:
        order = _MODEL_ORDER.get(app["app_label"])
        if order:
            rank = {name: i for i, name in enumerate(order)}
            app["models"].sort(key=lambda m: (rank.get(m["object_name"], len(rank)), m["name"]))
    return app_list


admin.AdminSite.get_app_list = _ordered_get_app_list

urlpatterns = [
    path('admin/', admin.site.urls),
]
