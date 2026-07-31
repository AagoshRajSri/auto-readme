from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def root_index(request):
    return JsonResponse({
        "message": "auto-readme DRF Backend API",
        "endpoints": {
            "generate": "/api/generate/",
            "status": "/api/status/<id>/"
        }
    })

urlpatterns = [
    path('', root_index, name='root-index'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

