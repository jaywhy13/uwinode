from django import template
from django.conf import settings
from django.template.loader import render_to_string

from lxml import etree
from geonode.maps.models import Layer
import httplib2
import urllib
import math

register = template.Library()


""" Util functions ==============================================
"""
def arr_get(arr, index, value):
    if(len(arr) <= index):
        return value
    else:
        return arr[index]

def combine_bboxes(bboxes):
    """ Combines bounding boxes
    """
    final_bbox = None
    for bbox in bboxes:
        if not final_bbox:
            final_bbox = bbox
        else:
            if bbox[0] < final_bbox[0]:
                final_bbox[0] = bbox[0]
            if bbox[2] < final_bbox[2]:
                final_bbox[2] = bbox[2]
    return final_bbox

def squarify_bbox(bbox):
    """ Transforms a rectangular bounding box into a square
    """
    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])
    
    dataAspect = 1 if dy == 0 else dx / dy
    
    if dataAspect > 1: # image is wide
        diff = float(dx - dy)
        bbox[0] = float(bbox[0]) - float(diff/2.0)
        bbox[1] = float(bbox[1]) + float(diff/2.0)
    else: # image is long
        diff = float(dy - dx)
        bbox[2] = float(bbox[2]) - float(diff/2.0)
        bbox[3] = float(bbox[3]) - float(diff/2.0)
    return bbox

def get_layer_bbox(layer):
    """ Returns the bounding box for a layer in the format: (lon1 lon2 lat1 lat2)
    """
    resource = layer.resource
    bbox = {}
    
    for i in range(0,4):
        bbox[i] = float(resource.latlon_bbox[i])
    return bbox


def pad_bbox(bbox, padding=0.3):
    """ Applies a padding to the bounding box (0-1.0)
    """
    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])

    # calculate the padding
    padding_x = padding * dx
    padding_y = padding * dy

    bbox[0] = float(bbox[0]) - padding_x
    bbox[1] = float(bbox[1]) + padding_x

    bbox[2] = float(bbox[2]) - padding_y
    bbox[3] = float(bbox[3]) + padding_y

    return bbox

def center_bbox(bbox):
    """ Centers the content in the bounding box based on its dims
    """
    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])
    
    dataAspect = 1 if dy == 0 else dx / dy
    
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
    return bbox

def adjust_bbox_for_google(bbox, size=90):
    """ Adjusts the bounding box so that it will match Google's nearest zoom level
    """
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

def format_bbox(layer, size=90, padding=0.3, google_padding=True):
    """ formats a bbox for a layer, giving it padding and adjusts it for Google maps bg
    """
    if size <= 0:
        size = 50

    width = size
    height = size

    if not layer:
        return 

    bbox = get_layer_bbox(layer)
    
    # pad the bbox
    bbox = pad_bbox(bbox, padding)

    # center the image and update the bounding boxes 
    bbox = center_bbox(bbox)

    # put in padding for google now
    if google_padding:
        # recalculate dx and dy
        bbox = adjust_bbox_for_google(bbox)

    return bbox


""" Gmaps functions ==============================================
"""
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

def get_gmaps_container_html(gmaps_thumbnail_src, content, size=90):
    """ Returns a div container for with gmaps as the bg and supplied content within it
    """
    div_html = "<div class='thumbmail' style=\"position:relative; width:%spx; height:%spx; background-image:url('%s')\">\n %s\n </div>" % (size, size, gmaps_thumbnail_src, content)
    return div_html

def get_img_thumbnail_html(layer, size=90, draw_background=True, map_layer=None):
    """ Returns the html for the image thumbnail. If the gmaps src is included, the image will be wrapped in a div
    """
    if map_layer:
        zindex = map_layer.stack_order

    else:
        zindex = 1

    context = {
        'layer' : layer,
        'map_layer' : map_layer,
        'size' : size,
        'zindex' : zindex,
        'draw_background' : draw_background
        }
    thumbnail_img_html = render_to_string('layer_thumbnail.html', context)

    return thumbnail_img_html



""" Url functions ==============================================
"""
def get_thumbnail_link(layer, size=90, bbox=None):
    """ returns the link for a layer given the size and an optional bbox
    """
    if not bbox:
        bbox = format_bbox(layer, size)

    bbox_string = ",".join([str(bbox[0]), str(bbox[2]), str(bbox[1]), str(bbox[3])])
    srs = 'EPSG:4326'

    url = settings.GEOSERVER_BASE_URL + "wms?" + urllib.urlencode({
            'service': 'WMS',
            'request': 'GetMap',
            'layers': layer.typename,
            'format': "image/png",
            'height': size,
            'width': size,
            'srs': srs,
            'bbox': bbox_string,
            'transparent' : 'True'
            })
    return url


def get_gmaps_thumbnail_link(layer, size=90, bbox=None):
    """ returns the link for a thumbnail for gmaps given a layer and it's size and optional bbox
    """
    if not bbox:
        bbox = format_bbox(layer, size)
    
    zoom = get_gmaps_zoom_level(bbox[1], bbox[0], size)
    center_lat = float((bbox[2] + bbox[3])/2)
    center_lon = float((bbox[0] + bbox[1])/2)
    
    url = "http://maps.googleapis.com/maps/api/staticmap?" + urllib.urlencode({
            'zoom' : zoom,
            'size' : '%sx%s' % (size,size),
            'maptype' : 'roadmap',
            'sensor' : 'false',
            'center' : '%s,%s' % (center_lat, center_lon)
            })
    return url


""" Template node functions ==============================================
"""
class LayerThumbnailNode(template.Node):
    """ This class represents a node that renders out the thumbnail for a layer
    """ 

    def __init__(self, layer_var_name, size=90):
        """ We store the name of the variable and the size if provided
        """
        self.layer_var_name = layer_var_name
        self.size = size
        
    def render(self, context, layer=None):
        """ Renders out a div with a gmaps bg and the img preview in an IMG node
        """
        self.layer = context[self.layer_var_name]

        thumbnail_src = get_thumbnail_link(self.layer, self.size)
        gmaps_thumbnail_src = get_gmaps_thumbnail_link(self.layer, self.size)
        html = get_img_thumbnail_html(self.layer, self.size)
        return html



class MapThumbnailNode(template.Node):
    def __init__(self, map_var_name, size=90):
        self.map_var_name = map_var_name
        self.size = size

    def render(self, context):
        # check on the size ... this might be a variable
        try:
            self.size = int(self.size)
        except Exception:
            self.size = int(context[self.size])

        map = context[self.map_var_name]

        layers = []
        map_layers = []
        bboxes = []

        # loop through and save the map layers, layers and bboxes
        for map_layer in map.layers: # TODO: check that the order is correct
            errs = []
            if map_layer.ows_url and map_layer.name.startswith("geonode:"):
                # TODO: Find a better way to ensure these are geonode layers
                try:
                    layer_name = map_layer.name[8:]
                    layer = Layer.objects.get(name=layer_name) # get the corresp layer
                    bbox = get_layer_bbox(layer)
                    bboxes.append(bbox)
                    layers.append(layer)
                    map_layers.append(map_layer)
                except Exception as e:
                    errs.append("exception %s for %s" % (e,map_layer.name))

            if len(errs):
                return ", ".join(errs)

        if not len(layers):
            return "Preview unavailable" # quit if we have no layers

       
        map_bbox = combine_bboxes(bboxes)
        map_bbox = squarify_bbox(map_bbox)
        
        # Now loop again and get the urls for each img
        i = 1
        img_html = ""
        for layer in layers:
            map_layer = map_layers[i-1]
            thumbnail_src = get_thumbnail_link(layer, self.size, bbox=map_bbox)
            img_html += get_img_thumbnail_html(layer, size=self.size, map_layer=map_layer, draw_background=False)
            i+=1

        gmaps_thumbnail_src = get_gmaps_thumbnail_link(layers[0], size=self.size, bbox=map_bbox)        
        div_html = get_gmaps_container_html(gmaps_thumbnail_src, img_html, size=self.size)

        return div_html


class ThumbnailLinkNode(template.Node):

    def __init__(self, layer_var_name, size=90, bbox_var_name=None):
        self.layer_var_name = layer_var_name
        self.size = size
        self.bbox_var_name = bbox_var_name

    def retrieve_context_vars(self, context):
        # get the variables from the context
        try: # a variable might be used... 
            self.size = int(self.size)
        except Exception:
            self.size = int(context[self.size])
            
        self.layer = context[self.layer_var_name]
        self.bbox = context.get(self.bbox_var_name, format_bbox(self.layer,self.size))
        

    def render(self, context):
        self.retrieve_context_vars(context)
        url = get_thumbnail_link(self.layer, self.size, self.bbox)
        return url


class GmapsThumbnailLinkNode(ThumbnailLinkNode):

    def render(self, context):
        self.retrieve_context_vars(context)
        url = get_gmaps_thumbnail_link(self.layer, self.size, self.bbox)
        return url



        
""" Custom template tags functions ==============================================
"""
@register.tag(name="layer_thumbnail")
def layer_thumbnail(parser, token):
    """ displays a thumbnail for a layer e.g. {% layer_thumbnail layer %}
    """
    pieces = token.split_contents()
    tag_name, layer = pieces[0], pieces[1]
    if len(pieces) >= 3:
        size = pieces[2]
    else:
        size = None
    return LayerThumbnailNode(layer, size)

@register.tag(name="map_thumbnail")
def map_thumbnail(parser, token):
    """ displays a thumbnail for the map e.g. {% map_thumbnail map %}
    """
    pieces = token.split_contents()
    tag_name, map = pieces[0], pieces[1]
    if len(pieces) is 3:
        size = pieces[2]
    else:
        size = 90
    return MapThumbnailNode(map, size)


@register.tag(name='gmaps_thumbnail_link')
def gmaps_thumbnail_link(parser, token):
    """ Returns a link for google maps static api map for a thumbnail bg for our layer
    """
    pieces = token.split_contents()
    tag_name, layer_var_name, size, bbox_var_name = pieces[0], pieces[1], arr_get(pieces,2,90), arr_get(pieces,3,None)
    return GmapsThumbnailLinkNode(layer_var_name, size, bbox_var_name)

@register.tag(name='thumbnail_link')
def thumbnail_link(parser, token):
    pieces = token.split_contents()
    tag_name, layer_var_name, size, bbox_var_name = pieces[0], pieces[1], arr_get(pieces,2,90), arr_get(pieces,3,None)
    return ThumbnailLinkNode(layer_var_name, size, bbox_var_name)

