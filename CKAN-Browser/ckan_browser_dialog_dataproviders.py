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
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor
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

                self.settings.load()
                selected_servers = self.settings.selected_ckan_servers.split('|')
                self.servers = []
                for cs_name in self.settings.custom_servers:
                    url = self.settings.custom_servers[cs_name]
                    si = ServerInstance(cs_name, cs_name, url, url, custom_entry=True)
                    si.selected = True if si.settings_key in selected_servers else False
                    self.servers.append(si)
                for entry in result:
                    url_api = None
                    if 'url-api' in entry:
                        url_api = entry['url-api']
                        if 'geothermaldata' not in url_api:
                            url_api = url_api.replace('http://', 'https://')
                        url_api += '/api/3/'
                    si = ServerInstance(entry['title'], entry['description'], entry['url'], url_api)
                    si.selected = True if si.settings_key in selected_servers else False
                    self.servers.append(si)

                for idx, server in enumerate(self.servers):
                    i = QStandardItem(server.title)
                    i.setData(server)
                    if server.api_url is not None:
                        if server.is_custom:
                            i.setBackground(QColor(0, 0, 255, 50))
                        i.setCheckable(True)
                        i.setCheckState(Qt.Checked if server.selected else Qt.Unchecked)
                        self.list_model.appendRow(i)
        finally:
            self.__update_server_count()
            QApplication.restoreOverrideCursor()

    def searchTermChanged(self, text):
        results = []
        for s in self.servers:
            if s.search(text) > 0:
                results.append(s)
        self.list_model.clear()

        if len(results) < 1:
            # early exit
            self.__update_server_count()
            return

        for result in sorted(results, key=lambda r: r.last_search_result, reverse=True):
            # debug: show score of string matching in title
            # i = QStandardItem(u'{} - {}'.format(result.last_search_result, result.title))
            i = QStandardItem(result.title)
            i.setData(result)
            if result.api_url is not None:
                if result.is_custom:
                    i.setBackground(QColor(0, 0, 255, 50))
                i.setCheckable(True)
                i.setCheckState(Qt.Checked if result.selected else Qt.Unchecked)
                self.list_model.appendRow(i)
        self.__update_server_count()

    def item_checked_changed(self, item):
        self.util.msg_log_debug(
            u'item changed, checked:{} item:{} item.data:{}'.format(
                item.checkState() == Qt.Checked,
                item,
                item.data()
            )
        )
        if item.checkState() == Qt.Unchecked:
            item.data().selected = False
            return

        for row in range(self.list_model.rowCount()):
            i = self.list_model.item(row, 0)
            if i != item and i.checkState() == Qt.Checked:
                i.setCheckState(Qt.Unchecked)

        item.data().selected = True if item.checkState() == Qt.Checked else False

    def save_btn_clicked(self):
        self.util.msg_log_debug('save clicked')
        selected_servers = [s.settings_key for s in self.servers if s.selected]
        if len(selected_servers) < 1:
            self.settings.save(self.settings.KEY_SELECTED_CKAN_SERVERS, '')
        else:
            self.util.msg_log_debug(u'selected servers: {}'.format(selected_servers))
            self.settings.selected_ckan_servers = '|'.join(selected_servers)
            self.settings.ckan_url = [s for s in self.servers if s.selected][0].api_url
            self.settings.save()

    def __update_server_count(self):
        txt = self.IDC_lbInstanceCount.text().format(
            len([s for s in self.servers if s.api_url is not None]),
            len(self.servers)
        )
        self.IDC_lbInstanceCount.setText(txt)
