from django.urls import path, re_path
from .views import GenerateReadmeAPIView, ReadmeDetailAPIView

urlpatterns = [
    re_path(r'^generate/?$', GenerateReadmeAPIView.as_view(), name='generate-readme'),
    re_path(r'^status/(?P<id>\d+)/?$', ReadmeDetailAPIView.as_view(), name='readme-status'),
]
