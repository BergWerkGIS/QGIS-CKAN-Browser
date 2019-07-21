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

import math
import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5 import QtGui, uic
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QListWidgetItem, QDialog, QMessageBox
from .ckan_browser_dialog_disclaimer import CKANBrowserDialogDisclaimer
from .ckan_browser_dialog_dataproviders import CKANBrowserDialogDataProviders
from .pyperclip import copy
from .ckanconnector import CkanConnector
from .util import Util


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ckan_browser_dialog_base.ui'))


class CKANBrowserDialog(QDialog, FORM_CLASS):

    def __init__(self, settings, iface, parent=None):
        """Constructor."""
        super(CKANBrowserDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.iface = iface
        self.main_win = parent
        self.search_txt = ''
        self.cur_package = None
        self.result_count = 0
        self.current_page = 1
        self.page_count = 0
        self.current_group = None
        # TODO:
        # * create settings dialog
        # * read SETTINGS

        self.settings = settings
        self.util = Util(self.settings, self.main_win)

        self.IDC_lblVersion.setText(self.IDC_lblVersion.text().format(self.settings.version))
        #self.IDC_lblSuchergebnisse.setText(self.util.tr('py_dlg_base_search_result'))
        self.IDC_lblPage.setText(self.util.tr('py_dlg_base_page_1_1'))

        icon_path = self.util.resolve(u'icon-copy.png')
        self.IDC_bCopy.setIcon(QtGui.QIcon(icon_path))

        self.cc = CkanConnector(self.settings, self.util)

        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.window_loaded)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        # don't initialized dialogs here, WaitCursor would be set several times
        # self.dlg_disclaimer = CKANBrowserDialogDisclaimer(self.settings)
        # self.dlg_dataproviders = CKANBrowserDialogDataProviders(self.settings, self.util)


    def showEvent(self, event):
        self.util.msg_log_debug('showevent')
        QDialog.showEvent(self, event)
        if self.timer is not None:
            self.timer.start(500)
        self.util.msg_log_debug('showevent finished')

    def window_loaded(self):
        try:
            self.settings.load()
            self.IDC_lblApiUrl.setText(self.util.tr('py_dlg_base_current_server').format(self.settings.ckan_url))
            self.IDC_lblCacheDir.setText(self.util.tr('py_dlg_base_cache_path').format(self.settings.cache_dir))
            if self.timer is not None:
                self.timer.stop()
                self.timer = None

            self.IDC_listResults.clear()
            self.IDC_listGroup.clear()
            self.IDC_textDetails.setText('')
            self.IDC_listRessources.clear()
            self.IDC_plainTextLink.setPlainText('')

            self.util.msg_log_debug('before get_groups')

            ok, result = self.cc.get_groups()
            if ok is False:
                QApplication.restoreOverrideCursor()
                self.util.dlg_warning(result)
                return

            if not result:
                self.list_all_clicked()
            else:
                for entry in result:
                    item = QListWidgetItem(entry['display_name'])
                    item.setData(Qt.UserRole, entry)
                    #item.setCheckState(Qt.Checked)
                    item.setCheckState(Qt.Unchecked)
                    self.IDC_listGroup.addItem(item)
        finally:
            QApplication.restoreOverrideCursor()

    def close_dlg(self):
        QDialog.reject(self)

    def show_disclaimer(self):
        self.dlg_disclaimer = CKANBrowserDialogDisclaimer(self.settings)
        self.dlg_disclaimer.show()

    def searchtextchanged(self, search_txt):
        self.search_txt = search_txt

    def suchen(self):
        self.current_page = 1
        self.current_group = None
        self.__search_package()

    def list_all_clicked(self):
        self.current_page = 1
        self.current_group = None
        # don't hint on wildcards, empty text works as well, as CKAN uses *:* as
        # default when ?q= has not text
        # self.IDC_lineSearch.setText('*:*')
        self.IDC_lineSearch.setText('')
        self.__search_package()

    def category_item_clicked(self, item):
        self.util.msg_log_debug(item.data(Qt.UserRole)['name'])
        self.current_group = item.data(Qt.UserRole)['name']
        self.current_page = 1
        self.__search_package()

    def select_data_provider_clicked(self):
        self.util.msg_log_debug('select data provider clicked')
        self.dlg_dataproviders = CKANBrowserDialogDataProviders(self.settings)
        self.dlg_dataproviders.show()
        if self.dlg_dataproviders.exec_():
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.window_loaded()

    def __search_package(self, page=None):
        self.IDC_listResults.clear()
        #if self.search_txt == u'' and self.current_group is None:
        #    return
        if page is not None:
            self.util.msg_log_debug(u'page is not None, cp:{0} pg:{1}'.format(self.current_page, page))
            self.current_page = self.current_page + page
            if self.current_page > self.page_count:
                self.current_page = self.page_count
            if self.current_page < 1:
                self.current_page = 1
            self.util.msg_log_debug(u'page is not None, cp:{0} pg:{1}'.format(self.current_page, page))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        if self.current_group is None:
            # normal query: limit query to checked groups, or all if unchecked
            self.util.msg_log_debug(u'normal query')
            groups = self.__get_selected_groups()
            ok, result = self.cc.package_search(self.search_txt, groups, self.current_page)
        else:
            # double click on group in list, ignore query and return all
            # packages for group
            self.util.msg_log_debug(u'query everything for group:{0}'.format(self.current_group))
            ok, result = self.cc.show_group(self.current_group, self.current_page)
        QApplication.restoreOverrideCursor()
        if ok is False:
            self.util.dlg_warning(result)
            return
        #if self.current_group is None:
        #    self.result_count = result['count']
        #else:
        #    self.result_count = len(result)
        self.result_count = result['count']
        if self.result_count == 0:
            self.current_page = 1
            self.page_count = 1
            self.IDC_lblSuchergebnisse.setText(self.util.tr('py_dlg_base_search_result_0'))
            item = QListWidgetItem(self.util.tr('py_dlg_base_no_result'))
            item.setData(Qt.UserRole, None)
            self.IDC_listResults.addItem(item)
            return

        # self.current_page = 1
        self.page_count = int(math.ceil(self.result_count / self.settings.results_limit))
        #if self.result_count % self.settings.results_limit != 0:
        #    self.page_count += 1
        erg_text = self.util.tr(u'py_dlg_base_result_count').format(self.result_count)
        self.util.msg_log_debug(erg_text)
        page_text = self.util.tr(u'py_dlg_base_page_count').format(self.current_page, self.page_count)
        self.IDC_lblSuchergebnisse.setText(erg_text)
        self.IDC_lblPage.setText(page_text)

        #if self.current_group is None:
        #    results = result['results']
        #else:
        #    results = result
        results = result['results']

        for entry in results:
            title_txt = u'no title available'
            if 'title' not in entry:
                continue
            e = entry['title']
            if e is None:
                title_txt = 'no title'
            elif isinstance(e, dict):
                # HACK! use first value
                title_txt = next(iter(list(e.values())))
            elif isinstance(e, list):
                # HACK! use first value
                title_txt = e[0]
            else:
                title_txt = e
            item = QListWidgetItem(title_txt)
            item.setData(Qt.UserRole, entry)
            self.IDC_listResults.addItem(item)

    def list_group_item_changed(self, item):
        self.searchtextchanged(self.IDC_lineSearch.text())

    def resultitemchanged(self, new_item):
        self.IDC_textDetails.setText('')
        self.IDC_listRessources.clear()
        self.IDC_plainTextLink.clear()
        if new_item is None:
            return
        package = new_item.data(Qt.UserRole)
        self.cur_package = package
        if package is None:
            return
        self.IDC_textDetails.setText(
            u'{0}\n\n{1}\n{2}\n\n{3}'.format(
                package.get('notes', 'no notes'),
                package.get('author', 'no author'),
                package.get('author_email', 'no author_email'),
                package.get('license_id', 'no license_id')
            )
        )
        if package.get('num_resources', 0) > 0:
            for res in package['resources']:
                item = QListWidgetItem(u'{0}: {1}'.format(
                    res.get('format', 'no format')
                    , res.get('name', 'no name')
                ))
                item.setData(Qt.UserRole, res)
                item.setCheckState(Qt.Unchecked)
                self.IDC_listRessources.addItem(item)

    def resource_item_changed(self, new_item):
        if new_item is None:
            return
        url = new_item.data(Qt.UserRole)['url']
        self.util.msg_log_debug(url)
        self.__fill_link_box(url)

    def load_resource_clicked(self):
        res = self.__get_selected_resources()
        if res is None:
            self.util.dlg_warning(self.util.tr(u'py_dlg_base_warn_no_resource'))
            return
        # self.util.dlg_warning(u'pkg:{0} res:{1} {2}'.format(self.cur_package['id'], res[0]['id'], res[0]['url']))
        for resource in res:
            if resource['name'] is None:
                # self.util.dlg_warning(self.util.tr(u'py_dlg_base_warn_no_resource_name').format(resource['id']))
                # continue
                resource['name'] = "Unnamed resource"
            self.util.msg_log_debug(u'Bearbeite: {0}'.format(resource['name']))
            dest_dir = os.path.join(
                self.settings.cache_dir,
                self.cur_package['id'],
                resource['id']
            )
            if self.util.create_dir(dest_dir) is False:
                self.util.dlg_warning(self.util.tr(u'py_dlg_base_warn_cache_dir_not_created').format(dest_dir))
                return

            dest_file = os.path.join(dest_dir, os.path.split(resource['url'])[1])

            # wmts
            format_lower = resource['format'].lower()
            if format_lower == 'wms':
                format_lower = 'wmts'
            if format_lower == 'wmts':
                resource_url = resource['url']
                resource_url_lower = resource_url.lower()
                if not resource_url_lower.endswith('.qlr'):
                    dest_file += '.wmts'
                #pyperclip.copy(resource_url)
                """
                self.util.dlg_information(u'{0}\n{1}\n\n{2}\n{3}\n{4}'.format(
                    u'WMTS kann nicht automatisch geladen werden.',
                    u'Der Link wurde in die Zwischenablage kopiert.',
                    u'Layer -> Layer hinzufügen -> ',
                    u'WMS/WMTS-Layer hinzufügen ->',
                    u'Neu -> im Textfeld "URL" Strg+V drücken'
                ))
                continue
                """
            if format_lower == 'wfs':
                dest_file += '.wfs'
            if format_lower == 'georss':
                dest_file += '.georss'

            do_download = True
            do_delete = False
            if os.path.isfile(dest_file):
                if QMessageBox.Yes == self.util.dlg_yes_no(self.util.tr(u'py_dlg_base_data_already_loaded')):
                    do_delete = True
                    do_download = True
                else:
                    do_download = False
            if do_download is True:
                # set wait cursor if request take it time, low latency, server not reachable, ...
                QApplication.setOverrideCursor(Qt.WaitCursor)
                QtWidgets.qApp.processEvents()
                file_size_ok, file_size, hdr_exception = self.cc.get_file_size(resource['url'])
                QApplication.restoreOverrideCursor()
                # Silently ignore the error
                if not file_size_ok:
                    file_size = 0
                if file_size > 50 and QMessageBox.No == self.util.dlg_yes_no(self.util.tr(u'py_dlg_base_big_file').format(file_size)):
                    continue  # stop process if user does not want to download the file
                if hdr_exception:
                    self.util.dlg_warning(u'{}'.format(hdr_exception))
                    continue

                self.util.msg_log_debug('setting wait cursor')
                QApplication.setOverrideCursor(Qt.WaitCursor)
                # pump GUI messages, otherwise wait cursor might not get displayed
                # as we are running the downloads on the main thread and if the request
                # gets stuck immediately (eg low latency or connection refused only after some time)
                # wait cursor might not appear
                QtWidgets.qApp.processEvents()
                self.util.msg_log_debug('wait cursor set')

                ok, err_msg, new_file_name = self.cc.download_resource(
                    resource['url']
                    , resource['format']
                    , dest_file
                    , do_delete
                )
                QApplication.restoreOverrideCursor()
                if ok is False:
                    #self.util.dlg_warning(self.util.tr(u'py_dlg_base_download_error').format(err_msg))
                    self.util.dlg_warning(err_msg)
                    continue
                # set new file name obtained from service 'content-disposition'
                if new_file_name:
                    dest_file = new_file_name
                if os.path.basename(dest_file).lower().endswith('.zip'):
                    ok, err_msg = self.util.extract_zip(dest_file, dest_dir)
                    QApplication.restoreOverrideCursor()
                    if ok is False:
                        self.util.dlg_warning(self.util.tr(u'py_dlg_base_warn_not_extracted').format(err_msg))
                        continue

            #QApplication.setOverrideCursor(Qt.WaitCursor)
            ok, err_msg = self.util.add_lyrs_from_dir(dest_dir, resource['name'], resource['url'])
            #QApplication.restoreOverrideCursor()
            if ok is False:
#                 self.util.dlg_warning(self.util.tr(u'py_dlg_base_lyr_not_loaded').format(resource['name'], err_msg))
                if isinstance(err_msg, dict):
                    if QMessageBox.Yes == self.util.dlg_yes_no(self.util.tr(u'py_dlg_base_open_manager').format(resource['url'])):
                        self.util.open_in_manager(err_msg["dir_path"])
                else:
                    self.util.dlg_warning(self.util.tr(u'py_dlg_base_lyr_not_loaded').format(resource['name'], err_msg))
                continue

    def next_page_clicked(self):
        self.__search_package(page=+1)

    def previous_page_clicked(self):
        self.__search_package(page=-1)

    def copy_clipboard(self):
        copy(self.IDC_plainTextLink.toPlainText())

    def __fill_link_box(self, url):
        self.IDC_plainTextLink.setPlainText(url)

    def __get_selected_groups(self):
        groups = []
        for i in range(0, self.IDC_listGroup.count()):
            item = self.IDC_listGroup.item(i)
            if item.checkState() == Qt.Checked:
                groups.append(item.data(Qt.UserRole)['name'])

        # None: means search all groups
        if len(groups) < 1 or len(groups) == self.IDC_listGroup.count():
            return None
        return groups

    def __get_selected_resources(self):
        res = []
        for i in range(0, self.IDC_listRessources.count()):
            item = self.IDC_listRessources.item(i)
            if item.checkState() == Qt.Checked:
                res.append(item.data(Qt.UserRole))

        if len(res) < 1:
            return None
        return res

    def _shorten_path(self, s):
        """ private class to shorten string to 33 chars and place a html-linebreak inside"""
        result = u""
        if len(s) > 33:
            result = s[:33] + u'<br />' + self._shorten_path(s[33:])
        else:
            return s
        return result

    def help_ttip_search(self):
        self.util.dlg_information(self.util.tr(u'dlg_base_ttip_search'))

    def help_ttip_filter(self):
        self.util.dlg_information(self.util.tr(u'dlg_base_ttip_filter'))

    def help_ttip_data_list(self):
        self.util.dlg_information(self.util.tr(u'dlg_base_ttip_data_list'))

    def help_ttip_resource(self):
        self.util.dlg_information(self.util.tr(u'dlg_base_ttip_resource'))
