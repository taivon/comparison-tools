from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from datetime import datetime


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages with individual priorities"""

    changefreq = "weekly"
    protocol = "https"

    # Define priorities for each page
    priorities = {
        "home": 1.0,  # Main landing page - highest priority
        "apartments:index": 0.9,  # Apartment comparison tool - very high priority
        "privacy": 0.4,  # Legal pages - lower priority
        "terms": 0.4,
        "homes": 0.3,  # Coming soon pages - lowest priority
        "hotels": 0.3,
    }

    # Define change frequencies for different page types
    changefreqs = {
        "home": "daily",  # Landing page changes more frequently
        "apartments:index": "weekly",
        "privacy": "monthly",
        "terms": "monthly",
        "homes": "monthly",
        "hotels": "monthly",
    }

    def items(self):
        """Return list of URL names for static pages"""
        return [
            "home",
            "apartments:index",
            "privacy",
            "terms",
            "homes",
            "hotels",
        ]

    def location(self, item):
        """Return the URL path for each item"""
        return reverse(item)

    def priority(self, item):
        """Return priority for each item"""
        return self.priorities.get(item, 0.5)

    def changefreq(self, item):
        """Return changefreq for each item"""
        return self.changefreqs.get(item, "weekly")

    def lastmod(self, item):
        """Return last modification date"""
        # You can customize this to track actual modification dates
        # For now, return current date for important pages
        if item in ["home", "apartments:index"]:
            return datetime.now()
        return None


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
