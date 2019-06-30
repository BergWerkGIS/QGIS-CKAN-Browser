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
from PyQt5.QtCore import QTimer, Qt, QStringListModel, QModelIndex, QObject, pyqtSignal, QEvent
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor
from PyQt5.QtWidgets import QDialog, QApplication, QListWidgetItem, QAction, QInputDialog, QLineEdit
from .ckanconnector import CkanConnector
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
        self.cc = CkanConnector(self.settings, self.util)

        self.clickable(self.IDC_lbl_enter_dataprovider_url).connect(self.lbl_clicked_enter_data_provider_url)
        self.list_model = QStandardItemModel(self)
        self.list_model.itemChanged.connect(self.item_checked_changed)
        self.IDC_listProviders.activated.connect(self.server_in_list_activated)
        self.IDC_listProviders.clicked.connect(self.server_in_list_clicked)
        self.IDC_listProviders.setModel(self.list_model)
        delete_custom_server_action = QAction('Delete', self.IDC_listProviders)
        delete_custom_server_action.triggered.connect(self.delete_custom_server)
        self.IDC_listProviders.addAction(delete_custom_server_action)
        # self.list_model.setHorizontalHeaderLabels(['CKAN Servers'])
        self.servers = []
        self.row_server_selected_in_list = -1
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
            if self.timer is not None:
                self.timer.stop()
                self.timer = None
            self.list_model.clear()
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
                self.util.msg_log_debug(u'{} custom servers'.format(len(self.settings.custom_servers)))
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

    def delete_custom_server(self):
        self.util.msg_log_debug('delete context menu clicked')
        if self.row_server_selected_in_list == -1:
            self.util.dlg_information(self.util.tr('py_dlg_data_providers_no_server_selected'))
            return
        server_to_remove_item = self.list_model.item(self.row_server_selected_in_list, 0)
        server_to_remove = server_to_remove_item.data()
        if not server_to_remove.is_custom:
            self.util.dlg_information(self.util.tr('py_dlg_data_providers_cannot_delete_sever_from_official_list'))
            return
        if server_to_remove.short_title in self.settings.custom_servers:
            self.util.msg_log_debug(u'deleting custom server: {}'.format(server_to_remove))
            del self.settings.custom_servers[server_to_remove.short_title]
        else:
            self.util.msg_log_debug(
                u'unable to delete custom server, not found: {}\n{}'
                .format(server_to_remove, self.settings.custom_servers)
            )
        self.servers.remove(server_to_remove)
        self.list_model.removeRow(self.row_server_selected_in_list)
        self.row_server_selected_in_list = -1

    def lbl_clicked_enter_data_provider_url(self):
        self.IDC_leManualUrl.setText('https://ckan0.cf.opendata.inter.sandbox-toronto.ca/api/3/')

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

    def btn_clicked_test_connection(self):
        self.util.msg_log_debug('btn_clicked_test_connection')

        api_url = self.IDC_leManualUrl.text()
        self.util.msg_log_debug('testing URL: {0}'.format(api_url))

        QApplication.setOverrideCursor(Qt.WaitCursor)
        ok, result = self.cc.test_groups(api_url)
        QApplication.restoreOverrideCursor()

        if not ok:
            self.util.dlg_warning(result)
            return
        else:
            self.util.dlg_information(self.util.tr(u'py_dlg_set_info_conn_succs'))

    def btn_clicked_add_connection(self):
        self.util.msg_log_debug('btn_clicked_add_connection')

        # let's do another sanity check if the provided url works
        # might have changed since the user tested it
        api_url = self.IDC_leManualUrl.text()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        ok, result = self.cc.test_groups(api_url)
        QApplication.restoreOverrideCursor()
        if not ok:
            self.util.dlg_warning(result)
            return

        server_name, ok_pressed = QInputDialog.getText(
            self,
            self.util.tr('py_dlg_data_providers_custom_server'),
            self.util.tr('py_dlg_data_providers_name_custom_server'),
            QLineEdit.Normal,
            ""
        )
        if not ok_pressed or server_name is None or server_name.isspace() or server_name == '':
            return

        if server_name in self.settings.custom_servers:
            self.util.dlg_warning(self.util.tr('py_dlg_data_providers_custom_server_name_exists').format(server_name))
            return

        self.settings.custom_servers[server_name] = api_url
        self.settings.save()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.window_loaded()

    def server_in_list_activated(self, model_index):
        self.util.msg_log_debug(u'server activated, model index: {}'.format(model_index))

    def server_in_list_clicked(self, model_index):
        self.util.msg_log_debug(
            u'server clicked, col:{} row:{} data:{} model:{}'
            .format(
                model_index.column(),
                model_index.row(),
                model_index.data(),
                model_index.model()
            )
        )
        self.row_server_selected_in_list = model_index.row()

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

        # deselect all available servers.
        # currently selected one might not be visible
        # because of current search criteria
        for server in self.servers:
            server.selected = False

        # now work on server visible in the list
        for row in range(self.list_model.rowCount()):
            i = self.list_model.item(row, 0)
            if i != item and i.checkState() == Qt.Checked:
                i.setCheckState(Qt.Unchecked)

        item.data().selected = True if item.checkState() == Qt.Checked else False

    def save_btn_clicked(self):
        self.util.msg_log_debug('save clicked')
        selected_servers = [s.settings_key for s in self.servers if s.selected]
        if len(selected_servers) < 1:
            self.settings.selected_ckan_servers = ''
            self.util.dlg_warning(self.util.tr('py_dlg_data_providers_no_server_selected'))
            return
        else:
            self.util.msg_log_debug(u'selected servers: {}'.format(selected_servers))
            self.settings.selected_ckan_servers = '|'.join(selected_servers)
            self.settings.ckan_url = [s for s in self.servers if s.selected][0].api_url
        self.settings.save()
        self.accept()

    def __update_server_count(self):
        txt = self.IDC_lbInstanceCount.text().format(
            len([s for s in self.servers if s.api_url is not None]),
            len(self.servers)
        )
        self.IDC_lbInstanceCount.setText(txt)

    def clickable(self, widget):
        # from https://wiki.python.org/moin/PyQt/Making%20non-clickable%20widgets%20clickable
        class Filter(QObject):
            clicked = pyqtSignal()

            def eventFilter(self, obj, event):
                if obj == widget:
                    if event.type() == QEvent.MouseButtonRelease:
                        if obj.rect().contains(event.pos()):
                            self.clicked.emit()
                            # The developer can opt for .emit(obj) to get the object within the slot.
                            return True
                return False

        widget_filter = Filter(widget)
        widget.installEventFilter(widget_filter)
        return widget_filter.clicked
