from django import template

from dashboard.jalali import to_jalali_str

register = template.Library()


@register.filter(name='jalali')
def jalali_filter(value, arg=''):
    """Usage: {{ dt|jalali }} or {{ dt|jalali:'time' }}"""
    with_time = str(arg).lower() in ('time', 'datetime', '1', 'true')
    return to_jalali_str(value, with_time=with_time)
