# -*- coding: utf-8 -*-

from PyQt4.QtCore import QSettings
from PyQt4.QtNetwork import QNetworkProxy
import os
import ConfigParser

class Settings:

    # http://ckan.data.ktn.gv.at/api/3/action/
    # http://ckan.data.ktn.gv.at/api/3
    def __init__(self):
        self.debug = True
        self.results_limit = 50
        # API timeout in seconds
        #self.request_timeout = 0.0001
        self.request_timeout = 15
        self.ckan_url = None
        self.cache_dir = None
        self.DLG_CAPTION = u'CKAN-Browser'
        self.KEY_CACHE_DIR = 'ckan_browser/cache_dir'
        self.KEY_CKAN_API = 'ckan_browser/ckan_api'
        self.version = self._determine_version()

    def load(self):
        qgis_settings = QSettings()
        self.cache_dir = qgis_settings.value(self.KEY_CACHE_DIR, '')
        if self.cache_dir is None:
            self.cache_dir = ''
#         self.ckan_url = qgis_settings.value(self.KEY_CKAN_API, 'http://ckan.data.ktn.gv.at/api/3/action/')
        self.ckan_url = qgis_settings.value(self.KEY_CKAN_API, '')
        if self.ckan_url is None:
            self.ckan_url = ''

    def save(self):
        qgis_settings = QSettings()
        qgis_settings.setValue(self.KEY_CACHE_DIR, self.cache_dir)
        qgis_settings.setValue(self.KEY_CKAN_API, self.ckan_url)

    def get_proxies(self):
        s = QSettings()
        # if user has never clicked on proxy settings in GUI,
        # this settings does not even exist -> default to 'false'
        proxy_enabled = s.value('proxy/proxyEnabled', 'false')
        proxy_type = s.value('proxy/proxyType', '')
        proxy_host = s.value('proxy/proxyHost', '')
        proxy_port = s.value('proxy/proxyPort', '')
        proxy_user = s.value('proxy/proxyUser', None)
        proxy_password = s.value('proxy/proxyPassword', None)
        if proxy_enabled == 'false' or not proxy_enabled:
            return False, None
        if proxy_type == 'HttpProxy':
            proxy_string = ''
            if proxy_user is not None and proxy_password is not None\
                    and proxy_user != '' and proxy_password != '':
                proxy_string += proxy_user + ':' + proxy_password + '@'
            proxy_string += proxy_host + ':' + proxy_port
            #print proxy_string
            return True, {
                'http': 'http://' + proxy_string,
                'https': 'https://' + proxy_string
            }


    def _determine_version(self):
        """http://gis.stackexchange.com/a/169266/8673"""
        # error handling?
        config = ConfigParser.ConfigParser()
        config.read(os.path.join(os.path.dirname(__file__),'metadata.txt'))
        
        return config.get('general', 'version')
        
"""

from PyQt4.QtCore import QSettings
from PyQt4.QtNetwork import QNetworkProxy

s = QSettings() #getting proxy from qgis options settings
proxyEnabled = s.value("proxy/proxyEnabled", "")
proxyType = s.value("proxy/proxyType", "" )
proxyHost = s.value("proxy/proxyHost", "" )
proxyPort = s.value("proxy/proxyPort", "" )
proxyUser = s.value("proxy/proxyUser", "" )
proxyPassword = s.value("proxy/proxyPassword", "" )
if proxyEnabled == "true": # test if there are proxy settings
   proxy = QNetworkProxy()
   if proxyType == "DefaultProxy":
       proxy.setType(QNetworkProxy.DefaultProxy)
   elif proxyType == "Socks5Proxy":
       proxy.setType(QNetworkProxy.Socks5Proxy)
   elif proxyType == "HttpProxy":
       proxy.setType(QNetworkProxy.HttpProxy)
   elif proxyType == "HttpCachingProxy":
       proxy.setType(QNetworkProxy.HttpCachingProxy)
   elif proxyType == "FtpCachingProxy":
       proxy.setType(QNetworkProxy.FtpCachingProxy)
   proxy.setHostName(proxyHost)
   proxy.setPort(int(proxyPort))
   proxy.setUser(proxyUser)
   proxy.setPassword(proxyPassword)
   QNetworkProxy.setApplicationProxy(proxy)

"""