# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CKAN-Browser
                                 A QGIS plugin
 Download and display CKAN enabled Open Data Portals
                              -------------------
        begin                : 2019-06-30
        git sha              : $Format:%H$
        copyright            : (C) 2019 by BergWerk GIS
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
import json
import os

from PyQt5 import QtGui, uic
from PyQt5.QtCore import QTimer, Qt, QStringListModel, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QDialog, QApplication, QListWidgetItem
from .httpcall import HttpCall
from .serverinstance import ServerInstance
from .util import Util

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(
        os.path.dirname(__file__),
        'ckan_browser_dialog_dataproviders.ui'
    )
)


class CKANBrowserDialogDataProviders(QDialog, FORM_CLASS):
    def __init__(self, settings, parent=None):
        """Constructor."""
        super(CKANBrowserDialogDataProviders, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setModal(True)
        self.setupUi(self)
        self.main_win = parent
        self.settings = settings
        self.util = Util(self.settings, self.main_win)
        self.list_model = QStandardItemModel(self)
        self.list_model.itemChanged.connect(self.item_checked_changed)
        self.IDC_listProviders.setModel(self.list_model)
        # self.list_model.setHorizontalHeaderLabels(['CKAN Servers'])
        self.servers = []
        self.util.msg_log_debug('CKANBrowserDialogDataProviders constructor')
        # self.IDC_grpManualDataProvider.collapsed = True
        # self.IDC_grpManualDataProvider.setCollapsed(True)
        #self.IDC_listProviders.setStyleSheet("QListWidget::item { border-bottom: 1px solid black; }");
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.window_loaded)
        QApplication.setOverrideCursor(Qt.WaitCursor)

    def showEvent(self, event):
        self.util.msg_log_debug('showevent')
        QDialog.showEvent(self, event)
        if self.timer is not None:
            self.timer.start(500)
        self.util.msg_log_debug('showevent finished')

    def window_loaded(self):
        try:
            self.timer.stop()
            self.timer = None
            instances_url = 'https://raw.githubusercontent.com/ckan/ckan-instances/gh-pages/config/instances.json'
            self.util.msg_log_debug('before getting instances: ' + instances_url)
            http_call = HttpCall(self.settings, self.util)
            response = http_call.execute_request(
                instances_url
                # , headers=self.ua_chrome
                , verify=False
                , stream=True
                , proxies=self.settings.get_proxies()[1]
                , timeout=self.settings.request_timeout
            )

            if not response.ok:
                QApplication.restoreOverrideCursor()
                self.util.dlg_warning(u'{}: {} {}'.format(response.status_code, response.status_message, response.reason))
                return
            else:
                try:
                    json_txt = response.text.data().decode()
                    self.util.msg_log_debug(u'resp_msg (decoded):\n{} .......'.format(json_txt[:255]))
                    result = json.loads(json_txt)
                except TypeError as te:
                    self.util.msg_log_error(u'unexpected TypeError: {0}'.format(te))
                    return False, self.util.tr(u'cc_api_not_accessible')
                except AttributeError as ae:
                    self.util.msg_log_error(u'unexpected AttributeError: {0}'.format(ae))
                    return False, self.util.tr(u'cc_api_not_accessible')
                except:
                    self.util.msg_log_error(u'unexpected error during request or parsing of response:')
                    self.util.msg_log_last_exception()
                    return False, self.util.tr(u'cc_invalid_json')

                instances_cnt = len(result)
                self.IDC_lbInstanceCount.setText(u'{} instances'.format(instances_cnt))
                self.util.msg_log_debug(u'{} instances'.format(instances_cnt))

                self.servers = []
                for entry in result:
                    url_api = entry['url-api'] if 'url-api' in entry else None
                    si = ServerInstance(entry['title'], entry['description'], url_api)
                    self.servers.append(si)

                for server in self.servers:
                    i = QStandardItem(server.title)
                    if server.api_url:
                        i.setBackground(Qt.green)
                    i.setData(server, Qt.UserRole)
                    i.setCheckable(True)
                    i.setCheckState(Qt.Unchecked)
                    self.list_model.appendRow(i)
                for i in range(self.list_model.rowCount()):
                    xx = self.list_model.item(i, 0)
                    self.util.msg_log_debug(u'itemdata {}'.format(xx.data(Qt.UserRole)))
        finally:
            QApplication.restoreOverrideCursor()

    def searchTermChanged(self, text):
        results = []
        for s in self.servers:
            if s.search(text) > 0:
                results.append(s)
        self.list_model.clear()
        if len(results) < 1:
            return
        self.IDC_lbInstanceCount.setText(u'{} instances'.format(len(results)))
        for result in sorted(results, key=lambda r: r.last_search_result, reverse=True):
            i = QStandardItem(u'{} - {}'.format(result.last_search_result, result.title))
            if result.api_url:
                i.setBackground(Qt.green)
            i.setCheckable(True)
            i.setCheckState(Qt.Unchecked)
            self.list_model.appendRow(i)

    def item_checked_changed(self, item):
        self.util.msg_log_debug(
            u'item changed, checked:{} item:{} item.data:{}'.format(
                item.checkState() == Qt.Checked,
                item,
                item.data(Qt.UserRole)
            )
        )
        if item.checkState() == Qt.Checked:
            data = item.data(Qt.UserRole)
            data.selected = True
            item.setData(data, Qt.UserRole)


    def save_btn_clicked(self):
        self.util.msg_log_debug('save clicked')

