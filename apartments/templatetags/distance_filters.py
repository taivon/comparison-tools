from django import template

register = template.Library()


@register.filter
def sort_by_time(distance_data):
    """
    Sort distance_data dict by travel_time (ascending).
    Items with None travel_time are sorted to the end.
    Returns a list of (label, info) tuples.
    """
    if not distance_data:
        return []

    def sort_key(item):
        label, info = item
        travel_time = info.get("travel_time")
        if travel_time is None:
            return (1, 9999)  # Sort None values to end
        return (0, travel_time)

    return sorted(distance_data.items(), key=sort_key)
