from uwinode.maps.views import *

LATEST_LIMIT = 3

def get_latest_maps(user):

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
            if user.has_perm('maps.view_map', obj=map):
                latest.append(map)
                if len(latest) >= limit:
                    break
    return maps

def get_latest_layers(user):

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
            if user.has_perm('maps.view_layer', obj=layer):
                latest.append(layer)
                if len(latest) >= limit:
                    break
    return latest
    

def home(request):
    layers = get_latest_layers(request.user)
    maps = get_latest_maps(request.user)
    context = {'layers' : layers, 'maps' : maps }
    return render_to_response("index.html", RequestContext(request,context))
