from django import template
from django.conf import settings
from lxml import etree
from geonode.maps.models import Layer
import httplib2
import urllib
import math

register = template.Library()

def get_gmaps_angle_for_zoom_level(zoom, width=90):
    """ This function gets the width (angle) that a given zoom level spans
    we use this information to adjust our bounding box so that it will fit
    Google maps backdrop image.
    """
    
    GLOBE_WIDTH = 256.0
    k = (360.0 / GLOBE_WIDTH)
    w = float(width)
    ln2 = math.log(2)
    z = float(zoom)
    
    pow = math.log(k * w) - (z * ln2)
    return math.pow(math.e,pow)

def get_gmaps_zoom_level(east_lon,west_lon, image_width=90):
    """ returns the zoom level for google maps given an east and west long coord
    """
    GLOBE_WIDTH = 256
    image_width = float(image_width)
    angle = float(east_lon) - float(west_lon)
    if angle < 0:
        angle += 360
    zoom = round(math.log(image_width * 360 / angle / GLOBE_WIDTH) / math.log(2))
    return int(zoom)

def format_bbox(layer, size=90, padding=0.3, google_padding=True):
    """ formats a bbox for a layer, giving it padding and so on
    """
    if size <= 0:
        size = 50

    width = size
    height = size

    if not layer:
        return 

    resource = layer.resource
    bbox = {}
    
    for i in range(0,4):
        bbox[i] = resource.latlon_bbox[i]

    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])

    # calculate the padding
    padding_x = padding * dx
    padding_y = padding * dy

    bbox[0] = float(bbox[0]) - padding_x
    bbox[1] = float(bbox[1]) + padding_x

    bbox[2] = float(bbox[2]) - padding_y
    bbox[3] = float(bbox[3]) + padding_y

    dataAspect = 1 if dy == 0 else dx / dy
    
    # center the image and update the bounding boxes 
    if dataAspect > 1:
        # center the image vertically
        padding = float((dy * dataAspect)-dy) / 2
        bbox[2] = float(bbox[2]) - padding
        bbox[3] = float(bbox[3]) + padding
    else:
        # handle longer than wide, center horizontally
        padding = float((dx * dataAspect)-dx) / 2
        bbox[0] = float(bbox[0]) - padding
        bbox[1] = float(bbox[1]) + padding

    # put in padding for google now
    if google_padding:
        # recalculate dx and dy
        dx = float(bbox[1]) - float(bbox[0])
        dy = float(bbox[3]) - float(bbox[2])

        google_zoom_level = get_gmaps_zoom_level(bbox[1], bbox[0], size)
        google_angle = get_gmaps_angle_for_zoom_level(google_zoom_level, size)
        
        google_padding_x = float((google_angle - dx)/2)
        google_padding_y = float((google_angle - dy)/2)
        
        bbox[0] = float(bbox[0]) - google_padding_x
        bbox[1] = float(bbox[1]) + google_padding_x

        bbox[2] = float(bbox[2]) - google_padding_y
        bbox[3] = float(bbox[3]) + google_padding_y

    return bbox


@register.filter(name='gmaps_thumbnail_link')
def gmaps_thumbnail_link(layer, size=90, center=True, mime="image/png"):
    """ Returns a link for google maps static api map for a thumbnail bg for our layer
    """
    bbox = format_bbox(layer, size)
    zoom = get_gmaps_zoom_level(bbox[1], bbox[0], size)

    center_lat = float((bbox[2] + bbox[3])/2)
    center_lon = float((bbox[0] + bbox[1])/2)
    
    url = "http://maps.googleapis.com/maps/api/staticmap?" + urllib.urlencode({
            'center' : '%s,%s' % (center_lat, center_lon),
            'zoom' : zoom,
            'size' : '%sx%s' % (size,size),
            'maptype' : 'roadmap',
            'sensor' : 'false'
            })
    return url

@register.filter(name='thumbnail_link')
def thumbnail_link(layer, size=90, center=True, mime="image/png"):
    """ Returns a thumbnail link for layer from Geoserver
    """
    bbox = format_bbox(layer, size)
    bbox_string = ",".join([str(bbox[0]), str(bbox[2]), str(bbox[1]), str(bbox[3])])
    srs = 'EPSG:4326'

    url = settings.GEOSERVER_BASE_URL + "wms?" + urllib.urlencode({
            'service': 'WMS',
            'request': 'GetMap',
            'layers': layer.typename,
            'format': mime,
            'height': size,
            'width': size,
            'srs': srs,
            'bbox': bbox_string,
            'transparent' : 'True'
            })
    return url


class ThumbnailNode(template.Node):
    """ This class represents a node that renders out the thumbnail for a layer
    """ 

    def __init__(self, layer_var_name, size=90):
        """ We store the name of the variable and the size if provided
        """
        self.layer_var_name = layer_var_name
        self.size = size
        
    def render(self, context):
        """ Renders out a div with a gmaps bg and the img preview in an IMG node
        """
        layer = context[self.layer_var_name]
        thumbnail_src = thumbnail_link(layer, self.size)
        gmaps_thumbnail_src = gmaps_thumbnail_link(layer, self.size)

        thumbnail_img_html = "<img src='%s' style='z-index:1; position:absolute; top:0px; left:0px;'/>" % thumbnail_src
        div_html = "<div class='layer_thumbmail' style='position:relative; backgroud-image:url(%s)'>\n %s\n </div>" % (gmaps_thumbnail_src, thumbnail_img_html)
        
        return div_html


@register.tag(name="layer_thumbnail")
def thumbnail(parser, token):
    """ displays a thumbnail for a layer e.g. {% thumbnail layer %}
    """
    pieces = token.split_contents()
    tag_name, layer = pieces[0], pieces[1]
    if len(pieces) is 3:
        size = pieces[2]
    else:
        size = 90
    return ThumbnailNode(layer, size)

