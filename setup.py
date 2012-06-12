import os
from distutils.core import setup

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

setup(
    name="uwinode",
    version="0.1",
    author="",
    author_email="",
    description="uwinode, based on GeoNode",
    long_description=(read('README.rst')),
    # Full list of classifiers can be found at:
    # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 1 - Planning',
    ],
    license="BSD",
    keywords="uwinode geonode django",
    url='https://github.com/uwinode/uwinode',
    packages=['uwinode',],
    include_package_data=True,
    zip_safe=False,
)
