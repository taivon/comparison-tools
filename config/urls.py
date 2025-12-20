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
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apartments import views as apartment_views
from apartments.sitemaps import StaticViewSitemap

# Sitemap configuration
sitemaps = {
    "static": StaticViewSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("__reload__/", include("django_browser_reload.urls")),
    # Main homepage showcasing all comparison tools
    path("", apartment_views.main_homepage, name="home"),
    # Comparison tool apps
    path(
        "apartments/",
        include(
            [
                path("", include("apartments.urls")),
                path("", include("feedback.urls", namespace="feedback")),
            ]
        ),
    ),
    path("homes/", apartment_views.homes_coming_soon, name="homes"),
    path("hotels/", apartment_views.hotels_coming_soon, name="hotels"),
    # Authentication (kept at root level for consistency)
    path("login/", apartment_views.login_view, name="login"),
    path("logout/", apartment_views.logout_view, name="logout"),
    path("signup/", apartment_views.signup_view, name="signup"),
    path("auth/", include("social_django.urls", namespace="social")),  # Google OAuth + One Tap
    path("auth/complete/", apartment_views.google_oauth_callback, name="oauth_callback"),
    # Legal pages (shared across all comparison tools)
    path("privacy/", apartment_views.privacy_policy, name="privacy"),
    path("terms/", apartment_views.terms_of_service, name="terms"),
    # SEO: Sitemap and Robots
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("robots.txt", apartment_views.robots_txt, name="robots_txt"),
]
