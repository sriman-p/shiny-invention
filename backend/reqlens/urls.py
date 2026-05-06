"""
Root URL configuration for the ReqLens Django project.

This is the top-level URL router that Django uses to dispatch incoming HTTP
requests. It defines two top-level URL prefixes:

  - /admin/  -> Django's built-in admin interface for database management
  - /api/v1/ -> All REST API endpoints defined in core.urls

The API is versioned (v1) in the URL path so that breaking changes can be
introduced under /api/v2/ without disrupting existing clients.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django admin interface for development and debugging
    path("admin/", admin.site.urls),
    # All REST API endpoints, versioned under /api/v1/
    path("api/v1/", include("core.urls")),
]
