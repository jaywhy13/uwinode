from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext, loader
from geonode.maps.models import *
from geonode.maps.views import *
from uwinode.views import get_latest_layers, get_latest_maps

def maps_search_page(request):
    # for non-ajax requests, render a generic search page

    if request.method == 'GET':
        params = request.GET
    elif request.method == 'POST':
        params = request.POST
    else:
        return HttpResponse(status=405)

    maps = get_latest_maps(request.user)

    return render_to_response('maps_search.html', RequestContext(request, {
                'latest_maps' : maps,
                'init_search': json.dumps(params or {}),
                "site" : settings.SITEURL
    }))



def show_search_page(request):
    DEFAULT_BASE_LAYERS = default_map_config()[1]
    # for non-ajax requests, render a generic search page

    if request.method == 'GET':
        params = request.GET
    elif request.method == 'POST':
        params = request.POST
    else:
        return HttpResponse(status=405)

    map_obj = Map(projection="EPSG:900913", zoom = 1, center_x = 0, center_y = 0)

    layers = get_latest_layers(request.user)

    return render_to_response('search.html', RequestContext(request, {
                'latest_layers' : layers,
                'init_search': json.dumps(params or {}),
                'viewer_config': json.dumps(map_obj.viewer_json(*DEFAULT_BASE_LAYERS)),
                'GOOGLE_API_KEY' : settings.GOOGLE_API_KEY,
                "site" : settings.SITEURL
    }))



def metadata_search_latest(request):
    if request.method == 'GET':
        params = request.GET
    elif request.method == 'POST':
        params = request.POST
    else:
        return HttpResponse(status=405)

    layers = Layer.objects.reverse()
    count = layers.count()
    limit = LATEST_LIMIT

    try:
        limit = int(params.get('limit', LATEST_LIMIT))
    except Exception:
        pass
    
    limit = min(limit, LATEST_LIMIT)
    
    latest = []
    
    if count:
        for layer in layers:
            if request.user.has_perm('maps.view_layer', obj=layer):
                latest.append(layer)
                if len(latest) >= limit:
                    break

    context = {
        "total" : limit,
        "layers" : latest
        }

    return render_to_response("maps/latest_layers.html", RequestContext(request, context))


def maps_search_latest(request):
    if request.method == 'GET':
        params = request.GET
    elif request.method == 'POST':
        params = request.POST
    else:
        return HttpResponse(status=405)

    maps = Map.objects.reverse()
    count = maps.count()
    limit = LATEST_LIMIT

    try:
        limit = int(params.get('limit', LATEST_LIMIT))
    except Exception:
        pass
    
    limit = min(limit, LATEST_LIMIT)
    
    latest = []

    if count:
        for map in maps:
            if request.user.has_perm('maps.view_map', obj=map):
                latest.append(map)
                if len(latest) >= limit:
                    break

    context = {
        "total" : limit,
        "maps" : latest
        }

    return render_to_response("maps/latest_maps.html", RequestContext(request, context))
