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

from django.urls import include, path
from django.contrib.sitemaps.views import sitemap
from apartments import views as apartment_views
from apartments.sitemaps import StaticViewSitemap, DashboardSitemap

# Sitemap configuration
sitemaps = {
    "static": StaticViewSitemap,
    "dashboard": DashboardSitemap,
}

urlpatterns = [
    # path("admin/", admin.site.urls),  # Disabled for Firestore-only setup
    path("__reload__/", include("django_browser_reload.urls")),
    path("", include("apartments.urls")),
    path("login/", apartment_views.login_view, name="login"),
    path("logout/", apartment_views.logout_view, name="logout"),
    path("signup/", apartment_views.signup_view, name="signup"),
    path("auth/", include("social_django.urls", namespace="social")),  # Google OAuth
    # SEO: Sitemap and Robots
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", apartment_views.robots_txt, name="robots_txt"),
]
