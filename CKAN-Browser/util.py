# -*- coding: utf-8 -*-

import errno
import glob
import os
from fnmatch import filter
import shutil
import subprocess
import sys
import zipfile
import json
from PyQt4.QtCore import \
    QCoreApplication, \
    QDateTime, \
    QDir, \
    QFile, \
    QFileInfo, \
    QIODevice, \
    QObject, \
    QSettings, \
    QUrl, \
    SIGNAL, \
    SLOT
from PyQt4.QtGui import QMessageBox
from PyQt4.QtXml import QDomNode, QDomElement, QDomDocument, QDomNodeList
from qgis.core import QgsMapLayerRegistry, QgsMessageLog, QgsVectorLayer, QgsRasterLayer, QgsProviderRegistry
from qgis.core import QgsLayerTreeGroup, QgsProject
from qgis._core import QgsMapLayer


class Util:

    def __init__(self, settings, main_win):
        self.main_win = main_win
        self.dlg_caption = settings.DLG_CAPTION
        self.settings = settings

    # Moved from ckan_browser.py
    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('CKANBrowser', message, encoding=QCoreApplication.UnicodeUTF8)

    def create_dir(self, dir_path):
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except OSError as ose:
                if ose.errno != errno.EEXIST:
                    return False
        return True

    def check_dir(self, dir_path):
        if (
            dir_path is None or
            dir_path.isspace() or
            dir_path == ''
        ):
            return False
        if os.path.isdir(dir_path):
            # TODO check write permissions
            return True
        return self.create_dir(dir_path)
    
    
    def check_api_url(self, api_url):
        if(
           not api_url or
           api_url is None or
           api_url.isspace() or
           api_url == ''
           ):
            return False
        else:
            return True

    def extract_zip(self, archive, dest_dir):
        try:
            # zf.extractall(dest_dir) fails for umlauts
            # https://github.com/joeferraro/MavensMate/pull/27/files
            f = zipfile.ZipFile(archive, 'r')
            self.msg_log(u'dest_dir: {0}'.format(dest_dir))

            for file_info in f.infolist():
                #file_name = os.path.join(dest_dir, file_info.filename.decode('utf8'))
                #decode('utf8') fails on Windows with umlauts in filenames
                file_name = os.path.join(dest_dir, file_info.filename)
                # different types of ZIPs
                # some have a dedicated entry for folders
                if file_name[-1] == u'/':
                    if not os.path.exists(file_name):
                        os.makedirs(file_name)
                    continue
                # some don't hava dedicated entry for folder
                # extract folder info from file name
                extract_dir = os.path.dirname(file_name)
                if not os.path.exists(extract_dir):
                    os.makedirs((extract_dir))
                out_file = open(file_name, 'wb')
                shutil.copyfileobj(f.open(file_info.filename), out_file)
            return True, None
        except UnicodeDecodeError as ude:
            return False, u'UnicodeDecodeError: {0}'.format(ude.reason)
        except AttributeError as ae:
            return False, u'AttributeError: {0}'.format(ae.message)
        except:
            self.msg_log(u'Except: {0}'.format(sys.exc_info()[1]))
            return False, u'Except: {0}'.format(sys.exc_info()[1])

    def add_lyrs_from_dir(self, data_dir, layer_name, layer_url):
        try:
            file_types = (
                '*.[Ss][Hh][Pp]',
                '*.[Gg][Mm][Ll]',
                '*.[Gg][Ee][Oo][Rr][Ss][Ss]',
                '*.[Xx][Mm][Ll]',
                '*.[Cc][Ss][Vv]',
                '*.[Tt][Xx][Tt]',
                '*.[Pp][Dd][Ff]',
                '*.[Tt][Ii][Ff]',
                '*.[Tt][Ii][Ff][Ff]',
                '*.[Aa][Ss][Cc]',
                '*.[Qq][Ll][Rr]',
                '*.[Ii][Mm][Gg]',
                '*.[Jj][2][Kk]',
                '*.[Jj][Pp][2]',
                '*.[Rr][Ss][Tt]',
                '*.[Dd][Ee][Mm]',
                '*.[Ww][Mm][Tt][Ss]',
                '*.[Ww][Mm][Ss]',
                '*.[Ww][Ff][Ss]',
                '*.[Kk][Mm][Ll]',
                '*.[Xx][Ll][Ss]',
                '*.[Xx][Ll][Ss][Xx]',
                '*.[Dd][Oo][Cc]',
                '*.[Dd][Oo][Cc][Xx]',
                '*.[Jj][Pp][Gg]',
                '*.[Jj][Pp][Ee][Gg]',
                '*.[Pp][Nn][Gg]',
                '*.*[Jj][Ss][Oo][Nn]'
            )
            geo_files = []
            for file_type in file_types:
                ### python 3.5
                # glob_term = os.path.join(data_dir, '**', file_type)
                # geo_files.extend(glob.glob(glob_term))
                ### python > 2.2
                for root, dir_names, file_names in os.walk(data_dir):
                    for file_name in filter(file_names, file_type):
                        geo_files.append(os.path.join(root, file_name))

            self.msg_log(u'add lyrs: {0}'.format(data_dir))
            self.msg_log(u'add lyrs: {0}'.format('\n'.join(geo_files)))

            if len(geo_files) < 1:
                self.msg_log('len(geo_files)<1')
#                 return False, u'Keine anzeigbaren Daten gefunden in\n{0}.\n\n\n     ===----!!!TODO!!!----===\n\nBenutzer anbieten Verzeichnis zu öffnen'.format(dir)
                return False, {"message": "unknown fileytpe", "dir_path": data_dir}
            for geo_file in geo_files:
                if os.path.basename(geo_file).lower().endswith('.shp.xml'):
                    self.msg_log(u'skipping {0}'.format(geo_file))
                    continue
                self.msg_log(geo_file)
                full_path = os.path.join(data_dir, geo_file)
                full_layer_name = layer_name + ' - ' + os.path.basename(geo_file)
                low_case = os.path.basename(geo_file).lower()
                lyr = None
                
                if low_case.endswith('json'): 
                    self.msg_log(u'Open JSON')
                    if False is self.__is_geojson(full_path):
                        if self.__open_with_system(full_path) > 0:
                            if QMessageBox.Yes == self.dlg_yes_no(self.tr(u'py_dlg_base_open_manager').format(layer_url)):
                                self.open_in_manager(data_dir)
                        continue
                
                if( 
                        low_case.endswith('.txt') or 
                        low_case.endswith('.pdf') or
                        low_case.endswith('.xls') or
                        low_case.endswith('.xlsx') or
                        low_case.endswith('.doc') or
                        low_case.endswith('.docx') or
                        low_case.endswith('.jpg') or
                        low_case.endswith('.jpeg') or
                        low_case.endswith('.png')
                    ):
                    if self.__open_with_system(full_path) > 0:
                        if QMessageBox.Yes == self.dlg_yes_no(self.tr(u'py_dlg_base_open_manager').format(layer_url)):
                            self.open_in_manager(data_dir)
                    continue
                elif low_case.endswith('.qlr'):
                    lyr = self.__add_layer_definition_file(
                        full_path,
                        QgsProject.instance().layerTreeRoot()
                    )
                elif low_case.endswith('.wmts') or low_case.endswith('.wms'): # for now, we assume it's a WMTS
                    self.msg_log(u'Open WM(T)S')
                    self._open_wmts(layer_name, layer_url)
                    continue
                elif low_case.endswith('.wfs'): # for now, we assume it's a WMTS
                    self.msg_log(u'Open WFS')
                    self._open_wfs(layer_name, layer_url)
                    continue
                elif low_case.endswith('.csv'):
#                     lyr = self.__add_csv_table(full_path, full_layer_name)
                    self.msg_log(u'Open CSV')
                    self._open_csv(full_path)
                    continue
                elif( 
                        low_case.endswith('.asc') or 
                        low_case.endswith('.tif') or 
                        low_case.endswith('.tiff') or 
                        low_case.endswith('.img') or 
                        low_case.endswith('.jp2') or 
                        low_case.endswith('.j2k') or 
                        low_case.endswith('.rst') or 
                        low_case.endswith('.dem')
                    ):
                    lyr = self.__add_raster_layer(full_path, full_layer_name)
                else:
                    lyr = self.__add_vector_layer(full_path, full_layer_name)
                if lyr is not None:
                    if not lyr.isValid():
                        self.msg_log(u'not valid: {0}'.format(full_path))
                        if QMessageBox.Yes == self.dlg_yes_no(self.tr(u'py_dlg_base_open_manager').format(layer_url)):
                            self.open_in_manager(data_dir)
                        continue
                    QgsMapLayerRegistry.instance().addMapLayer(lyr)
                else:
                    self.msg_log(u'could not add layer: {0}'.format(full_path))
            return True, None
        except AttributeError as ae:
            return False, ae.message
        except TypeError as te:
            return False, te.message
        except:
            return False, sys.exc_info()[0]

    def __add_vector_layer(self, file_name, full_layer_name):
        self.msg_log(u'vector layer'.format(file_name))
        lyr = QgsVectorLayer(
            file_name,
            full_layer_name,
            'ogr'
        )
        return lyr

    def __add_raster_layer(self, file_name, full_layer_name):
        self.msg_log(u'raster layer'.format(file_name))
        lyr = QgsRasterLayer(
            file_name,
            full_layer_name
        )
        return lyr

    def __add_csv_table(self, file_name, full_layer_name):
        self.msg_log(u'csv layer'.format(file_name))
        # file:///f:/scripts/map/points.csv?delimiter=%s&
        # file:///home/bergw/open-data-ktn-cache-dir/42b67af7-f795-48af-9de0-25c8d777bb50/d5ea898b-2ee7-4b52-9b7d-412826d73e45/schuler-und-klassen-kaernten-gesamt-sj-2014-15.csv?encoding=ISO-8859-1&type=csv&delimiter=;&geomType=none&subsetIndex=no&watchFile=no
        # file:///C:/Users/bergw/_TEMP/open-data-ktn-cache-2/wohnbevgemeinzeljahre-2014-WINDOWS.csv?encoding=windows-1252&type=csv&delimiter=%5Ct;&geomType=none&subsetIndex=no&watchFile=no
        slashes = '//'
        if os.name == 'nt':
            slashes += '/'
        lyr_src = u'file:{0}{1}?encoding=ISO-8859-1&type=csv&delimiter=;&geomType=none&subsetIndex=no&watchFile=no'.format(
            slashes,
            file_name
        )
        lyr = QgsVectorLayer(
            lyr_src,
            full_layer_name,
            'delimitedtext'
        )
        return lyr

    def __add_layer_definition_file(self, file_name, root_group):
        """
        shamelessly copied from
        https://github.com/qgis/QGIS/blob/master/src/core/qgslayerdefinition.cpp
        """
        qfile = QFile(file_name)
        if not qfile.open(QIODevice.ReadOnly):
            return None
        doc = QDomDocument()
        if not doc.setContent(qfile):
            return None
        file_info = QFileInfo(qfile)
        QDir.setCurrent(file_info.absoluteDir().path())
        root = QgsLayerTreeGroup()
        ids = doc.elementsByTagName('id')
        for i in xrange(0, ids.size()):
            id_node = ids.at(i)
            id_elem = id_node.toElement()
            old_id = id_elem.text()
            layer_name = old_id[:-17]
            date_time = QDateTime.currentDateTime()
            new_id = layer_name + date_time.toString('yyyyMMddhhmmsszzz')
            id_elem.firstChild().setNodeValue(new_id)
            tree_layer_nodes = doc.elementsByTagName('layer-tree-layer')
            for j in xrange(0, tree_layer_nodes.count()):
                layer_node = tree_layer_nodes.at(j)
                layer_elem = layer_node.toElement()
                if old_id == layer_elem.attribute('id'):
                    layer_node.toElement().setAttribute('id', new_id)
        layer_tree_elem = doc.documentElement().firstChildElement('layer-tree-group')
        load_in_legend = True
        if not layer_tree_elem.isNull():
            root.readChildrenFromXML(layer_tree_elem)
            load_in_legend = False
        layers = QgsMapLayer.fromLayerDefinition(doc)
        QgsMapLayerRegistry.instance().addMapLayers(layers, load_in_legend)
        nodes = root.children()
        for node in nodes:
            root.takeChild(node)
        del root
        root_group.insertChildNodes(-1, nodes)
        return None

    def _open_wmts(self, name, capabilites_url):
        # Add new HTTPConnection like in source
        # https://github.com/qgis/QGIS/blob/master/src/gui/qgsnewhttpconnection.cpp
        
        self.msg_log(u'add WM(T)S: Name = {0}, URL = {1}'.format(name, capabilites_url))
        
        s = QSettings()
        
        s.setValue(u'Qgis/WMS/{0}/password'.format(name), '')
        s.setValue(u'Qgis/WMS/{0}/username'.format(name), '')
        s.setValue(u'Qgis/connections-wms/{0}/dpiMode'.format(name), 7)  # refer to https://github.com/qgis/QGIS/blob/master/src/gui/qgsnewhttpconnection.cpp#L229-L247
        s.setValue(u'Qgis/connections-wms/{0}/ignoreAxisOrientation'.format(name), False)
        s.setValue(u'Qgis/connections-wms/{0}/ignoreGetFeatureInfoURI'.format(name), False)
        s.setValue(u'Qgis/connections-wms/{0}/ignoreGetMapURI'.format(name), False)
        s.setValue(u'Qgis/connections-wms/{0}/invertAxisOrientation'.format(name), False)
        s.setValue(u'Qgis/connections-wms/{0}/referer'.format(name), '')
        s.setValue(u'Qgis/connections-wms/{0}/smoothPixmapTransform'.format(name), False)
        s.setValue(u'Qgis/connections-wms/{0}/url'.format(name), capabilites_url)
        
        s.setValue(u'Qgis/connections-wms/selected', name)
        
        # create new dialog
        wms_dlg = QgsProviderRegistry.instance().selectWidget("wms", self.main_win)
        
        QObject.connect(wms_dlg, SIGNAL( "addRasterLayer( QString const &, QString const &, QString const & )" ),
                   self.main_win, SLOT( "addRasterLayer( QString const &, QString const &, QString const & )" ) )
        
        wms_dlg.show()
        
        
    def _open_wfs(self, name, capabilites_url):
        # Add new HTTPConnection like in source
        # https://github.com/qgis/QGIS/blob/master/src/gui/qgsnewhttpconnection.cpp
        # https://github.com/qgis/QGIS/blob/79616fd8d8285b4eb93adafdfcb97a3e429b832e/src/app/qgisapp.cpp#L3783
        
        self.msg_log(u'add WFS: Name={0}, original URL={1}'.format(name, capabilites_url))

        # remove additional url parameters, otherwise adding wfs works the frist time only
        # https://github.com/qgis/QGIS/blob/9eee12111567a84f4d4de7e020392b3c01c28598/src/gui/qgsnewhttpconnection.cpp#L199-L214
        url = QUrl(capabilites_url)
        url.removeQueryItem('SERVICE')
        url.removeQueryItem('REQUEST')
        url.removeQueryItem('FORMAT')
        url.removeQueryItem('service')
        url.removeQueryItem('request')
        url.removeQueryItem('format')
        #also remove VERSION: shouldn't be necessary, but QGIS sometimes seems to append version=1.0.0
        url.removeQueryItem('VERSION')
        url.removeQueryItem('version')

        capabilites_url = url.toString()
        self.msg_log(u'add WFS: Name={0}, base URL={1}'.format(name, capabilites_url))

        s = QSettings()

        self.msg_log(u'existing WFS url: {0}'.format(s.value(u'Qgis/connections-wfs/{0}/url'.format(name), '')))

        key_user = u'Qgis/WFS/{0}/username'.format(name)
        key_pwd = u'Qgis/WFS/{0}/password'.format(name)
        key_referer = u'Qgis/connections-wfs/{0}/referer'.format(name)
        key_url = u'Qgis/connections-wfs/{0}/url'.format(name)

        s.remove(key_user)
        s.remove(key_pwd)
        s.remove(key_referer)
        s.remove(key_url)
        s.sync()

        s.setValue(key_user, '')
        s.setValue(key_pwd, '')
        s.setValue(key_referer, '')
        s.setValue(key_url, capabilites_url)
        
        s.setValue(u'Qgis/connections-wfs/selected', name)
        
        # create new dialog
        wfs_dlg = QgsProviderRegistry.instance().selectWidget("WFS", self.main_win)
        
        QObject.connect(
            wfs_dlg
            , SIGNAL("addWfsLayer( QString, QString )")
            , self.main_win, SLOT("addWfsLayer( QString, QString )")
        )
        
        wfs_dlg.show()
        #wfs_dlg.exec()
        
        
    def _open_csv(self, full_path):
        # Add new HTTPConnection like in source
        # https://github.com/qgis/QGIS/blob/master/src/gui/qgsnewhttpconnection.cpp
        
        self.msg_log(u'add CSV file: {0}'.format(full_path))
        
        # create new dialog
        csv_dlg = QgsProviderRegistry.instance().selectWidget("delimitedtext", self.main_win)
        
        QObject.connect(csv_dlg, SIGNAL( "addVectorLayer( QString, QString, QString )" ),
                        self.main_win, SLOT( "addSelectedVectorLayer( QString, QString, QString )" ) )
        
        csv_dlg.children()[1].children()[2].setText(full_path)
        
        csv_dlg.show()
        

    def __open_with_system(self, file_name):
        code = None
        if sys.platform.startswith('darwin'):
            code = subprocess.call(('open', file_name))
        elif os.name == 'nt':
            win_code = os.startfile(file_name)
            if win_code != 0:
                code = -1
        elif os.name == 'posix':
            code = subprocess.call(('xdg-open', file_name))
        self.msg_log(u'Exit Code: {0}'.format(code))
        return code

    def __is_geojson(self, file_path):
        try:
            with open(file_path) as json_file:    
                data = json.load(json_file)
                
                if data.get('features') is not None:
                    self.msg_log('is_geojson: "features" found')
                    return True
                elif data.get('type') =="FeatureCollection":
                    self.msg_log('is_geojson: "FeatureCollection" found')
                    return True
                else:
                    return False
        except:
            self.msg_log(u'Error reading json'.format(sys.exc_info()[1]))
            return False

    def dlg_information(self, msg):
        QMessageBox.information(self.main_win, self.dlg_caption, msg)

    def dlg_warning(self, msg):
        QMessageBox.warning(self.main_win, self.dlg_caption, msg)

    def dlg_yes_no(self, msg):
        return QMessageBox.question(
            self.main_win,
            self.dlg_caption,
            msg,
            QMessageBox.Yes,
            QMessageBox.No
        )

    def msg_log(self, msg):
        if self.settings.debug is True:
            QgsMessageLog.logMessage(msg, self.dlg_caption)


    def resolve(self, name, basepath=None):
        """http://gis.stackexchange.com/a/130031/8673"""
        if not basepath:
            basepath = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(basepath, name)
    
    
    def open_in_manager(self, file_path):
        """http://stackoverflow.com/a/6631329/1504487"""
        if sys.platform == 'darwin':
            subprocess.Popen(['open', file_path])
        elif sys.platform == 'linux2':
            subprocess.Popen(['xdg-open', file_path])
        elif os.name == 'nt':
            subprocess.Popen(['explorer', file_path])
    
            
    def str2bool(self, v):
        """http://stackoverflow.com/a/715468/1504487"""
        return v.lower() in ("yes", "true", "t", "1")