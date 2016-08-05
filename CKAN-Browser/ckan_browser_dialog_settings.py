# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CKAN-Browser
                                 A QGIS plugin
 Download and display CKAN enabled Open Data Portals
                              -------------------
        begin                : 2014-10-24
        git sha              : $Format:%H$
        copyright            : (C) 2014 by BergWerk GIS
        email                : wb@BergWerk-GIS.at
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
from PyQt4.QtCore import Qt
from PyQt4 import QtGui, uic
from PyQt4.QtGui import QApplication, QDialog, QFileDialog
from collections import OrderedDict
from util import Util
from ckanconnector import CkanConnector
import json

try:
    from qgis.gui import QgsAuthConfigSelect
except ImportError:
    QgsAuthConfigSelect = None


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ckan_browser_dialog_settings.ui'))

class CKANBrowserDialogSettings(QtGui.QDialog, FORM_CLASS):
    def __init__(self, settings, iface, parent=None):
        """Constructor."""
        super(CKANBrowserDialogSettings, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.iface = iface
        self.main_win = parent
        self.settings = settings
        self.util = Util(self.settings, self.main_win)

        self.IDC_leCacheDir.setText(self.settings.cache_dir)
        self.IDC_leCkanApi.setText(self.settings.ckan_url)
        if QgsAuthConfigSelect is None:
            self.IDC_leAuthCfg.hide()
            self.IDC_bAuthCfgClear.hide()
            self.IDC_bAuthCfgEdit.hide()
            self.IDC_lblAuthCfg.hide()
        else:
            self.IDC_leAuthCfg.setText(self.settings.authcfg)

        self.cc = CkanConnector(self.settings, self.util)

        self.pre_ckan_apis = None
        self.fill_combobox();

    def fill_combobox(self):
        """ Fill Combobox with predefined CKAN API Urls """
        try:
            json_path = self.util.resolve(u'CKAN_APIs.json')
            with open(json_path) as json_file:
                self.pre_ckan_apis = json.load(json_file, object_pairs_hook=OrderedDict)

            for key in self.pre_ckan_apis.keys():
                self.IDC_cbPreCkanApi.addItem(key)

            value = self.pre_ckan_apis.itervalues().next()
            self.IDC_lblPreCkan.setText(value)

        except IOError as err:
            self.util.dlg_warning(self.util.tr(u"py_dlg_set_warn_urls_not_load").format(err))


    def select_cache_dir(self):
        cache_dir = QFileDialog.getExistingDirectory(
            self.main_win,
            self.settings.DLG_CAPTION,
            self.settings.cache_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if '' == cache_dir:
            self.util.msg_log('no cachedir selected')
        else:
            self.IDC_leCacheDir.setText(cache_dir)


    def test_ckan_url(self):
        """ Test if URL in LineEdit is a valid CKAN API URL """
        api_url = self.IDC_leCkanApi.text()
        self.util.msg_log('URL: {0}'.format(api_url))

        QApplication.setOverrideCursor(Qt.WaitCursor)
        ok, result = self.cc.test_groups(api_url)
        QApplication.restoreOverrideCursor()

        if ok is False:
            self.util.dlg_warning(result)
            return
        else:
            self.util.dlg_information(self.util.tr(u"py_dlg_set_info_conn_succs"))

#         for entry in result:
#             self.util.msg_log('Item: {0}'.format(entry))


    def pre_ckan_api(self):
        """select CKAN API from predefined file"""
        try:
            key = self.IDC_cbPreCkanApi.currentText()
            value = self.pre_ckan_apis[key]
            self.IDC_lblPreCkan.setText(value)
        except TypeError as err:
            self.util.msg_log('Error: No items in Preselected-Combo-Box: {0}'.format(err))
            pass


    def choose_pre_api(self):
        value = self.IDC_lblPreCkan.text()
        self.IDC_leCkanApi.setText(value)

    def cancel(self):
        QDialog.reject(self)

    def save(self):
        cache_dir = self.IDC_leCacheDir.text()
        if self.util.check_dir(cache_dir) is False:
            self.util.dlg_warning(
                self.util.tr(u'py_dlg_set_warn_cache_not_use').format(self.settings.cache_dir)
            )
            return

        # check URL - must not be empty
        api_url = self.IDC_leCkanApi.text()
        if self.util.check_api_url(api_url) is False:
            self.util.dlg_warning(self.util.tr(u'py_dlg_set_warn_ckan_url'))
            return

        self.settings.cache_dir = cache_dir
        self.settings.ckan_url = api_url

        authcfg = self.IDC_leAuthCfg.text()
        self.settings.authcfg = authcfg

        self.settings.save()

        QDialog.accept(self)

    def help_cache_dir(self):
        self.util.dlg_information(self.util.tr(u'dlg_set_tool_cache'))

    def help_pre_urls(self):
        self.util.dlg_information(self.util.tr(u'dlg_set_tool_pre_urls'))

    def help_api_url(self):
        self.util.dlg_information(self.util.tr(u'dlg_set_tool_api_url'))

    def authcfg_clear(self):
         self.IDC_leAuthCfg.clear()

    def authcfg_edit(self):
        dlg = QDialog(None)
        dlg.setWindowTitle(self.util.tr("Select Authentication"))
        layout = QtGui.QVBoxLayout(dlg)

        acs = QgsAuthConfigSelect(dlg)
        if self.IDC_leAuthCfg.text():
            acs.setConfigId(self.IDC_leAuthCfg.text())
        layout.addWidget(acs)

        buttonbox = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel,
            Qt.Horizontal, dlg
        )

        layout.addWidget(buttonbox)
        buttonbox.accepted.connect(dlg.accept)
        buttonbox.rejected.connect(dlg.close)

        dlg.setLayout(layout)
        dlg.setWindowModality(Qt.WindowModal)

        if dlg.exec_():
            self.IDC_leAuthCfg.setText(acs.configId())
