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
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QDialog, QApplication, QListWidgetItem
from .httpcall import HttpCall
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
        self.util.msg_log_debug('CKANBrowserDialogDataProviders constructor')
        self.IDC_grpManualDataProvider.collapsed = True
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
                for entry in result:
                    item = QListWidgetItem(u'{} - {}'.format(entry['title'], entry['description']))
                    item.setData(Qt.UserRole, entry)
                    #item.setCheckState(Qt.Checked)
                    item.setCheckState(Qt.Unchecked)
                    self.IDC_listProviders.addItem(item)
        finally:
            QApplication.restoreOverrideCursor()
