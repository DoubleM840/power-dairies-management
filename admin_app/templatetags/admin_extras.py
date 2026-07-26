from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Usage: {{ my_dict|get_item:key_variable }}
    Returns dictionary[key] or None if key is missing.
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
