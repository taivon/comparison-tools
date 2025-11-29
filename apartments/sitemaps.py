from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from datetime import datetime


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages with individual priorities"""

    changefreq = "weekly"
    protocol = "https"

    # Define priorities for each page
    priorities = {
        "apartments:index": 1.0,  # Apartment comparison tool - highest priority
        "home": 0.9,  # Main landing page - second highest
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


