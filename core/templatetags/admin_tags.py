from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()

@register.simple_tag
def try_url(view_name, *args, **kwargs):
    try:
        return reverse(view_name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return "#"