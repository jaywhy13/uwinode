from django import template
from django.conf import settings
from django.template.loader import render_to_string

from lxml import etree
from geonode.maps.models import Layer
import httplib2
import urllib
import math

register = template.Library()

DEFAULT_THUMBNAIL_SIZE = 90

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

    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])
    print "Layer orig ratio is: %s" % (dx/dy)

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

    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])
    print "Layer ratio after padding is: %s" % (dx/dy)


    return bbox

def scale_bbox(bbox, width, height):
    """ scales a given bbox into the dimensions given
    """
    if width == height:
        return bbox

    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])

    ratio = dx / dy
    target_ratio = float(width) / float(height)
    
    if ratio == target_ratio:
        return bbox

    #print "Pre-scaling"
    #print "Source: dx: %s, dy: %s, ratio: %s" % (dx, dy, ratio)
    #print "Target: %s, height: %s, ratio: %s" % (width, height, target_ratio)
    #print bbox
    
    if target_ratio >= 1:
        # the target is wider than long
        if ratio >= 1:
            if ratio >= target_ratio: 
                # consider scaling 4x1 to 10x5
                print "Scaling in here..."
                padding_y = ((dx / target_ratio) - dy)/2.0
                bbox[2] = float(bbox[2]) - padding_y
                bbox[3] = float(bbox[3]) + padding_y
            else:
                # consider scale 4x3 to 10x5
                padding_x = ((target_ratio * dy) - dx)/2.0
                bbox[0] = float(bbox[0]) - padding_x
                bbox[1] = float(bbox[1]) + padding_x
        else: # ratio is less than one
            # consider scaling 1x3 to 10x5
            padding_x = ((target_ratio * dy) - dx)/2.0
            bbox[0] = float(bbox[0]) - padding_x
            bbox[1] = float(bbox[1]) + padding_x
    else:
        # the target ratio is longer than wide
        # consider scaling 4x2 to 2x5
        if ratio >= 1:
            padding_y = ((dx/target_ratio)-dy)/2.0
            bbox[2] = float(bbox[2]) - padding_y
            bbox[3] = float(bbox[3]) + padding_y
        else:
            if ratio < target_ratio:
                # consider scaling 1x4 to 2x5
                padding_x = ((target_ratio * dy) - dx)/2.0
                bbox[0] = float(bbox[0]) - padding_x
                bbox[1] = float(bbox[1]) + padding_x
            else:
                # consider scaling 3x4 to 2x5
                padding_y = ((dx/target_ratio)-dy)/2.0
                bbox[2] = float(bbox[2]) - padding_y
                bbox[3] = float(bbox[3]) + padding_y


    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])
    ratio = dx / dy
    #print "Post-scaling"
    #print "Source: dx: %s, dy: %s, ratio: %s" % (dx, dy, ratio)
    #print "Target: %s, height: %s, ratio: %s" % (width, height, target_ratio)
    #print bbox

    print "Layer ratio after scaling is: %s" % (dx/dy)

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

    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])
    print "Layer ratio after centering is: %s" % (dx/dy)

    return bbox

def adjust_bbox_for_google(bbox, width=DEFAULT_THUMBNAIL_SIZE, height=None):
    """ Adjusts the bounding box so that it will match Google's nearest zoom level
    """
    if not height:
        height = width

    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])

    print "Ratio before google adjustments: %s" % (dx/dy)
    
    google_zoom_level = float(get_gmaps_zoom_level(bbox[1], bbox[0], float(width)))
    google_angle = get_gmaps_angle_for_zoom_level(google_zoom_level, float(width))

    print "Google zoom level is: %s, and angle is: %s, dx is %s" % (google_zoom_level, google_angle, dx)
    google_padding_x = float((dx - google_angle)/2.0)
    google_padding_y = (((google_padding_x * 2.0)/ dx) * dy)/2

    print "Padding selected is: (%s, %s)" % (google_padding_x, google_padding_y)
    
    bbox[0] = float(bbox[0]) - google_padding_x
    bbox[1] = float(bbox[1]) + google_padding_x
    
    bbox[2] = float(bbox[2]) - google_padding_y
    bbox[3] = float(bbox[3]) + google_padding_y

    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])


    print "Layer ratio after google adjustment is %s/%s = %s" % (dx,dy,dx/dy)
    print "Bbox returned by google is: %s" % bbox


    
    return bbox

def format_bbox(layer, width=DEFAULT_THUMBNAIL_SIZE, height=None, padding=0.3, google_padding=True):
    """ formats a bbox for a layer, giving it padding and adjusts it for Google maps bg
    """
    if width <= 0:
        width = DEFAULT_THUMBNAIL_SIZE

    width = width

    if not height:
        height = width

    if not layer:
        return 

    bbox = get_layer_bbox(layer)
    
    # pad the bbox
    bbox = pad_bbox(bbox, padding)

    # scale the bbox
    if width != height:
        bbox = scale_bbox(bbox, width, height)
    else:
        # center the image and update the bounding boxes 
        bbox = center_bbox(bbox)

    # put in padding for google now
    if google_padding:
        # recalculate dx and dy
        bbox = adjust_bbox_for_google(bbox)


    dx = float(bbox[1]) - float(bbox[0])
    dy = float(bbox[3]) - float(bbox[2])
    print "Layer ratio after formatting is %s/%s = %s" % (dx,dy,dx/dy)
    print "Bbox formatting now returns is: %s" % bbox

    return bbox


""" Gmaps functions ==============================================
"""
def get_gmaps_angle_for_zoom_level(zoom, width=DEFAULT_THUMBNAIL_SIZE):
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

def get_gmaps_zoom_level(east_lon,west_lon, image_width=DEFAULT_THUMBNAIL_SIZE):
    """ returns the zoom level for google maps given an east and west long coord
    """
    GLOBE_WIDTH = 256
    image_width = float(image_width)
    angle = float(east_lon) - float(west_lon)
    if angle < 0:
        angle += 360
    zoom = round(math.log(image_width * 360 / angle / GLOBE_WIDTH) / math.log(2))
    return int(zoom)

def get_gmaps_container_html(gmaps_thumbnail_src, content, width=DEFAULT_THUMBNAIL_SIZE, height=None):
    """ Returns a div container for with gmaps as the bg and supplied content within it
    """
    if not height:
        height = width


    div_html = "<div class='thumbmail' style=\"position:relative; width:%spx; height:%spx; background-image:url('%s')\">\n %s\n </div>" % (width, height, gmaps_thumbnail_src, content)
    return div_html

def get_img_thumbnail_html(layer, width=DEFAULT_THUMBNAIL_SIZE, height=None, draw_background=True, map_layer=None):
    """ Returns the html for the image thumbnail.
    """
    if map_layer:
        zindex = map_layer.stack_order

    else:
        zindex = 1

    if not height:
        height = width

    context = {
        'layer' : layer,
        'map_layer' : map_layer,
        'width' : width,
        'height' : height,
        'zindex' : zindex,
        'draw_background' : draw_background
        }
    thumbnail_img_html = render_to_string('layer_thumbnail.html', context)

    return thumbnail_img_html



""" Url functions ==============================================
"""
def get_thumbnail_link(layer, width=DEFAULT_THUMBNAIL_SIZE, height=None, bbox=None):
    """ returns the link for a layer given the width and an optional bbox
    """
    if not height:
        height = width


    if not bbox:
        bbox = format_bbox(layer, width)

    bbox_string = ",".join([str(bbox[0]), str(bbox[2]), str(bbox[1]), str(bbox[3])])
    srs = 'EPSG:4326'

    url = settings.GEOSERVER_BASE_URL + "wms?" + urllib.urlencode({
            'service': 'WMS',
            'request': 'GetMap',
            'layers': layer.typename,
            'format': "image/png",
            'height': width,
            'width': width,
            'srs': srs,
            'bbox': bbox_string,
            'transparent' : 'True'
            })
    return url


def get_gmaps_thumbnail_link(layer, width=DEFAULT_THUMBNAIL_SIZE, height=None, bbox=None):
    """ returns the link for a thumbnail for gmaps given a layer and it's width and optional bbox
    """
    if not height:
        height = width

    if not bbox:
        bbox = format_bbox(layer, width, height)
    
    zoom = get_gmaps_zoom_level(bbox[1], bbox[0], width)
    center_lat = float((bbox[2] + bbox[3])/2.0)
    center_lon = float((bbox[0] + bbox[1])/2.0)
    
    url = "http://maps.googleapis.com/maps/api/staticmap?" + urllib.urlencode({
            'zoom' : zoom,
            'size' : '%sx%s' % (width,height),
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

    def __init__(self, layer_var_name, width=DEFAULT_THUMBNAIL_SIZE, height=None):
        """ We store the name of the variable and the width if provided
        """
        self.layer_var_name = layer_var_name
        self.width = width
        self.height = height

        if not self.height:
            self.height = self.width

        
    def render(self, context, layer=None):
        """ Renders out a div with a gmaps bg and the img preview in an IMG node
        """
        self.layer = context[self.layer_var_name]

        html = get_img_thumbnail_html(self.layer, width=self.width, height=self.height)
        return html



class MapThumbnailNode(template.Node):
    def __init__(self, map_var_name, width=DEFAULT_THUMBNAIL_SIZE, height=None):
        self.map_var_name = map_var_name
        self.width = width
        self.height = height

        if not self.height:
            self.height = self.width


    def render(self, context):
        # check on the width ... this might be a variable
        try:
            self.width = int(self.width)
        except Exception:
            self.width = int(context[self.width])

        try:
            self.height = int(self.height)
        except Exception:
            self.height = int(context[self.height])

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
        map_bbox = scale_bbox(map_bbox, self.width, self.height)
        #map_bbox = squarify_bbox(map_bbox)
        
        # Now loop again and get the urls for each img
        i = 1
        img_html = ""
        for layer in layers:
            map_layer = map_layers[i-1]
            thumbnail_src = get_thumbnail_link(layer, width=self.width, height=self.height, bbox=map_bbox)
            img_html += get_img_thumbnail_html(layer, width=self.width, height=self.height, map_layer=map_layer, draw_background=False)
            i+=1

        gmaps_thumbnail_src = get_gmaps_thumbnail_link(layers[0], width=self.width, height=self.height, bbox=map_bbox)        
        div_html = get_gmaps_container_html(gmaps_thumbnail_src, img_html, width=self.width, height=self.height)

        return div_html


class ThumbnailLinkNode(template.Node):

    def __init__(self, layer_var_name, width=DEFAULT_THUMBNAIL_SIZE, height=None, bbox_var_name=None):
        self.layer_var_name = layer_var_name
        self.width = width
        self.height = height
        if not self.height:
            self.height = self.width

        self.bbox_var_name = bbox_var_name

    def retrieve_context_vars(self, context):
        # get the variables from the context
        try: # a variable might be used... 
            self.width = int(self.width)
        except Exception:
            self.width = int(context[self.width])

        try:
            self.height = int(self.height)
        except Exception:
            self.height = int(context[self.height])
            
        self.layer = context[self.layer_var_name]
        self.bbox = context.get(self.bbox_var_name, format_bbox(self.layer,self.width, self.height))

    def render(self, context):
        self.retrieve_context_vars(context)
        url = get_thumbnail_link(self.layer, self.width, self.height, self.bbox)
        return url


class GmapsThumbnailLinkNode(ThumbnailLinkNode):

    def render(self, context):
        self.retrieve_context_vars(context)
        url = get_gmaps_thumbnail_link(self.layer, self.width, self.height, self.bbox)
        return url


        
""" Custom template tags functions ==============================================
"""
@register.tag(name="layer_thumbnail")
def layer_thumbnail(parser, token):
    """ displays a thumbnail for a layer e.g. {% layer_thumbnail layer %}
    """
    pieces = token.split_contents()
    tag_name, layer = pieces[0], pieces[1]
    width = arr_get(pieces,2,DEFAULT_THUMBNAIL_SIZE)
    height = arr_get(pieces,3,width)

    return LayerThumbnailNode(layer, width, height)

@register.tag(name="map_thumbnail")
def map_thumbnail(parser, token):
    """ displays a thumbnail for the map e.g. {% map_thumbnail map width height %}
    """
    pieces = token.split_contents()
    print pieces
    tag_name, map = pieces[0], pieces[1]
    try:
        width = int(arr_get(pieces, 2, DEFAULT_THUMBNAIL_SIZE))
    except Exception as e:
        print e
        width = DEFAULT_THUMBNAIL_SIZE

    height = arr_get(pieces, 3, width)
    return MapThumbnailNode(map, width, height)


@register.tag(name='gmaps_thumbnail_link')
def gmaps_thumbnail_link(parser, token):
    """ Returns a link for google maps static api map for a thumbnail bg for our layer
    """
    pieces = token.split_contents()
    tag_name, layer_var_name, width, height, bbox_var_name = pieces[0], pieces[1], arr_get(pieces,2,DEFAULT_THUMBNAIL_SIZE), arr_get(pieces,3,None), arr_get(pieces,4,None)
    return GmapsThumbnailLinkNode(layer_var_name, width, height, bbox_var_name)

@register.tag(name='thumbnail_link')
def thumbnail_link(parser, token):
    pieces = token.split_contents()
    tag_name, layer_var_name, width, height, bbox_var_name = pieces[0], pieces[1], arr_get(pieces,2,DEFAULT_THUMBNAIL_SIZE), arr_get(pieces,3,None), arr_get(pieces,4,None)
    return ThumbnailLinkNode(layer_var_name, width, height, bbox_var_name)

