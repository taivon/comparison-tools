from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages"""

    priority = 0.8
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        """Return list of URL names for static pages"""
        return [
            "apartments:index",
            "apartments:privacy",
            "apartments:terms",
        ]

    def location(self, item):
        """Return the URL path for each item"""
        return reverse(item)


class DashboardSitemap(Sitemap):
    """Sitemap for authenticated user pages"""

    priority = 0.6
    changefreq = "daily"
    protocol = "https"

    def items(self):
        """Return list of URL names for dashboard pages"""
        return [
            "apartments:dashboard",
        ]

    def location(self, item):
        """Return the URL path for each item"""
        return reverse(item)
