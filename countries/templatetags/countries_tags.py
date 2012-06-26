#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django import template
from django.template.defaultfilters import stringfilter
from countries.models import *
from googlemaps import GoogleMaps
from django.conf import settings
from uwinode.templatetags.layer_extras import get_layer_center


register = template.Library()

def iso_flag(iso, flag_path=u''):
	"""
	Returns a full path to the ISO 3166-1 alpha-2 country code flag image.
	
	Example usage::
		
		{{ user_profile.country.iso|iso_flag }}
		
		{{ user_profile.country.iso|iso_flag:"appmedia/flags/%s.png" }}
	
	"""
	from countries.utils.isoflag import iso_flag
	return iso_flag(iso, flag_path)
iso_flag = stringfilter(iso_flag)

def layer_flag(layer):
	if layer:
		center = get_layer_center(layer)
		gmaps = GoogleMaps(settings.GOOGLE_API_KEY)
		lat = center.get('lat',None)
		lng = center.get('lng', None)
		if lat and lng:
			addr = gmaps.latlng_to_address(lat, lng)
			pieces = addr.split(",")
			country = pieces[-1].strip()
			flag_location = country_flag(country)
			return "<img src='%s'/>" % flag_location
	return ""


def country_flag(country):
	"""
	Returns a full path to the ISO 3166-1 alpha-2 country code flag image based on the country name
	"""
	if not country:
		return u''
	result = Country.objects.filter(name__icontains=country)
	if result:
		c = result[0]
		iso = c.iso
		flag_location = iso_flag(iso)
		return flag_location
	return u''

# Syntax: register.filter(name of filter, callback)
register.filter('iso_flag', iso_flag)
register.filter('country_flag', country_flag)
register.filter('layer_flag', layer_flag)
