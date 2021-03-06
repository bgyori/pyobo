# -*- coding: utf-8 -*-

"""Utilities for OBO files."""

import logging
import os
from typing import Optional
from urllib.request import urlretrieve

import obonet
from tqdm import tqdm

from .path_utils import ensure_path, get_prefix_obo_path
from .registries import CURATED_URLS, get_obofoundry
from .sources import CONVERTED, get_converted_obo
from .struct import Obo

__all__ = [
    'get',
    'MissingOboBuild',
    'NoOboFoundry',
]

logger = logging.getLogger(__name__)


class MissingOboBuild(RuntimeError):
    """Raised when OBOFoundry doesn't track an OBO file, but only has OWL."""


class NoOboFoundry(ValueError):
    """Raised when OBO foundry doesn't have it."""


def get(prefix: str, *, url: Optional[str] = None, local: bool = False) -> Obo:
    """Get the OBO for a given graph.

    :param prefix: The prefix of the ontology to look up
    :param url: A URL to give if the OBOfoundry can not be used to look up the given prefix
    :param local: A local file path is given. Do not cache.
    """
    path = f'{get_prefix_obo_path(prefix)}.obonet.json.gz'
    if os.path.exists(path) and not local:
        return Obo.from_obonet_gz(path)

    if prefix in CONVERTED:  # these graphs are converted in :mod:`pyobo.sources`
        obo = get_converted_obo(prefix)
        logger.info('[%s] caching OBO at %s', prefix, path)
        obo.write_default()
    else:
        obo = _get_obo_via_obonet(prefix=prefix, url=url, local=local)

    if not local:
        logger.info('[%s] caching pre-compiled OBO at %s', prefix, path)
        obo.write_obonet_gz(path)

    return obo


def _get_obo_via_obonet(prefix: str, *, url: Optional[str] = None, local: bool = False) -> Obo:
    """Get the OBO file by prefix or URL."""
    if url is None:
        path = _ensure_obo_path(prefix)
    elif local:
        path = url
    else:
        path = get_prefix_obo_path(prefix)
        if not os.path.exists(path):
            logger.info('[%s] downloading OBO from %s to %s', prefix, url, path)
            urlretrieve(url, path)

    logger.info('[%s] parsing with obonet from %s', prefix, path)
    with open(path) as file:
        graph = obonet.read_obo(tqdm(file, unit_scale=True, desc=f'[{prefix}] parsing obo'))
    if 'ontology' not in graph.graph:
        logger.warning('[%s] missing "ontology" key', prefix)
        graph.graph['ontology'] = prefix
    elif not graph.graph['ontology'].isalpha():
        logger.warning('[%s] ontology=%s has a strange format. replacing with prefix', prefix, graph.graph['ontology'])
        graph.graph['ontology'] = prefix
    return Obo.from_obonet(graph)


def _ensure_obo_path(prefix: str) -> str:
    """Get the path to the OBO file and download if missing."""
    if prefix in CURATED_URLS:
        curated_url = CURATED_URLS[prefix]
        logger.debug('[%s] checking for OBO at curated URL: %s', prefix, curated_url)
        return ensure_path(prefix, url=curated_url)

    path = get_prefix_obo_path(prefix)
    if os.path.exists(path):
        logger.debug('[%s] OBO already exists at %s', prefix, path)
        return path

    obofoundry = get_obofoundry(mappify=True)
    entry = obofoundry.get(prefix)
    if entry is None:
        raise NoOboFoundry(f'OBO Foundry is missing the prefix: {prefix}')

    build = entry.get('build')
    if build is None:
        raise MissingOboBuild(f'OBO Foundry is missing a build for: {prefix}')

    url = build.get('source_url')
    if url is None:
        raise MissingOboBuild(f'OBO Foundry build is missing a URL for: {prefix}, {build}')

    return ensure_path(prefix, url)
