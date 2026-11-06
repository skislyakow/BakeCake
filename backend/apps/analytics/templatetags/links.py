from django import template

from apps.analytics.reporting import campaign_link_rows as build_campaign_link_rows

register = template.Library()


@register.simple_tag
def campaign_link_rows():
    return build_campaign_link_rows()
