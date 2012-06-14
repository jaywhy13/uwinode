from django.template import TemplateDoesNotExist
from django.conf import settings

def load_template_source(template_name, template_dirs = None):
    if not template_dirs:
        template_dirs = settings.TEMPLATE_DIRS

    for template_dir in template_dirs:
        template_location = "%s/%s" % (template_dir, template_name)
        try:
            file_contents = open(template_location).read()
            icon = "<img src='http://cdn1.iconfinder.com/data/icons/PixeloPhilia_2/PNG/link.png' style='width:24px'>"
            caption = template_location
            if len(caption) > 30:
                caption = template_location[:27] + "..."
            header = "<span title='%s' style='font-family:Verdana;'>%s <u>template</u>: %s</span><br/>" % (template_location, icon, caption)
            file_contents = header + file_contents
            return (file_contents, template_name)
        except IOError:
            continue
        raise TemplateDoesNotExist, template_name

load_template_source.is_usable = True
