# -*- coding: utf-8 -*-

from PyQt5.QtCore import QSettings
import os
import configparser

from qgis.core import QgsMessageLog, Qgis


class Settings:

    def __init__(self):
        self.debug = True
        self.results_limit = 50
        self.request_timeout = 15
        self.ckan_url = None
        self.selected_ckan_servers = ''
        self.custom_servers = {}
        self.authcfg = None
        self.cache_dir = None
        self.DLG_CAPTION = u'CKAN-Browser'
        self.KEY_CACHE_DIR = 'ckan_browser/cache_dir'
        self.KEY_CKAN_API = 'ckan_browser/ckan_api'
        self.KEY_AUTHCFG = 'ckan_browser/authcfg'
        self.KEY_AUTH_PROPAGATE = 'ckan_browser/auth_propagate'
        self.KEY_SELECTED_CKAN_SERVERS = 'ckan_browser/selected_ckan_servers'
        self.KEY_CUSTOM_SERVERS = 'ckan_browser/custom_ckan_servers'
        self.KEY_SHOW_DEBUG_INFO = 'ckan_browser/show_debug_info'
        self.version = self._determine_version()

    def load(self):
        qgis_settings = QSettings()
        self.cache_dir = qgis_settings.value(self.KEY_CACHE_DIR, '')
        if self.cache_dir is None:
            self.cache_dir = ''
        self.ckan_url = qgis_settings.value(self.KEY_CKAN_API, 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/')
        self.selected_ckan_servers = qgis_settings.value(self.KEY_SELECTED_CKAN_SERVERS, '')
        self.custom_servers = qgis_settings.value(self.KEY_CUSTOM_SERVERS, {})
        self.debug = qgis_settings.value(self.KEY_SHOW_DEBUG_INFO, False, bool)
        self.authcfg = qgis_settings.value(self.KEY_AUTHCFG, '')
        self.auth_propagate = qgis_settings.value(self.KEY_AUTH_PROPAGATE, False, bool)

    def save(self):
        qgis_settings = QSettings()
        qgis_settings.setValue(self.KEY_CACHE_DIR, self.cache_dir)
        qgis_settings.setValue(self.KEY_CKAN_API, self.ckan_url)
        qgis_settings.setValue(self.KEY_AUTHCFG, self.authcfg)
        qgis_settings.setValue(self.KEY_AUTH_PROPAGATE, self.auth_propagate)
        qgis_settings.setValue(self.KEY_SELECTED_CKAN_SERVERS, self.selected_ckan_servers)
        qgis_settings.setValue(self.KEY_CUSTOM_SERVERS, self.custom_servers)
        qgis_settings.setValue(self.KEY_SHOW_DEBUG_INFO, self.debug)

    def _determine_version(self):
        """http://gis.stackexchange.com/a/169266/8673"""
        # error handling?
        config = configparser.ConfigParser()
        config.read(os.path.join(os.path.dirname(__file__), 'metadata.txt'))

        return config.get('general', 'version')
