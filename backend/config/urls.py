from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def api_root(request):
    return JsonResponse(
        {
            "name": "NewsHub API",
            "version": "1.0",
            "endpoints": {
                "news": "/api/news/",
                "search": "/api/news/search/?q=topic",
                "trending": "/api/news/trending/",
                "categories": "/api/categories/",
                "auth": "/api/auth/login/",
                "fact_check": "/api/fact-check/",
                "ml_metrics": "/api/ml/metrics/",
                "docs": "See README.md for the full endpoint list",
            },
        }
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("api/", include("news.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "NewsHub Administration"
admin.site.site_title = "NewsHub Admin"
admin.site.index_title = "Manage news content and users"
