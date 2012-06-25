from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext, loader
from geonode.maps.models import *

def metadata_search_latest(request):
    if request.method == 'GET':
        params = request.GET
    elif request.method == 'POST':
        params = request.POST
    else:
        return HttpResponse(status=405)

    LATEST_LIMIT = 1

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

    LATEST_LIMIT = 1

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
