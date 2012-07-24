from django.conf.urls.defaults import patterns, url
from uwinode.maps.views import metadata_search_latest
import uwinode.maps
import uwinode.maps.urls

datapatterns = patterns('uwinode.maps.views',
  url(r'^search/latest/$', 'metadata_search_latest', name='data_search_latest'),
  url(r'^search/?$', 'show_search_page', name='data_search'),
)

urlpatterns = patterns('uwinode.maps.views',
    url(r'^search/latest?$', 'maps_search_latest', name='maps_search_latest'),
    url(r'^search/?$', 'maps_search_page', name='maps_search'),
)
