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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from ckan_browser_dialog import CKANBrowserDialog
from ckan_browser_dialog_settings import CKANBrowserDialogSettings
import os.path
from settings import Settings
from util import Util


class CKANBrowser:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        QSettings().setValue("ckan_browser/isopen", False)
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'CKANBrowser_{}.qm'.format(locale))
        
        # load english file for testing
#         locale_path = os.path.join(
#             self.plugin_dir,
#             'i18n',
#             'CKANBrowser_en.qm')
        
        if not os.path.exists(locale_path):
            locale_path = os.path.join(
                self.plugin_dir,
                'i18n',
                'CKANBrowser_en.qm')
        
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        self.settings = Settings()
        self.settings.load()
        self.util = Util(self.settings, self.iface.mainWindow())

        # TODO ping API

        # Create the dialog (after translation) and keep reference
#         self.dlg = CKANBrowserDialog(self.settings, self.iface, self.iface.mainWindow())

        # Declare instance attributes
        self.actions = []
        self.menu = self.util.tr(u'&Open Data (CKAN) Browser')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'Open Data (CKAN) Browser')
        self.toolbar.setObjectName(u'Open Data (CKAN) Browser')


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the InaSAFE toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/CKANBrowser/icon.png'

        self.add_action(
            icon_path,
            text=self.util.tr(u'Open Data (CKAN) Browser'),
            callback=self.run,
            parent=self.iface.mainWindow()
        )
        
        icon_settings = ':/plugins/CKANBrowser/icon-settings.png'
        
        self.add_action(
            icon_settings,
            text=self.util.tr(u'ckan_browser_settings'),
            callback=self.open_settings,
            parent=self.iface.mainWindow()
        )

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.util.tr(u'&Open Data (CKAN) Browser'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""
        
        is_open = QSettings().value("ckan_browser/isopen", False)
        #Python treats almost everything as True````
        #is_open = bool(is_open)
        self.util.msg_log(u'isopen: {0}'.format(is_open))
        
        #!!!string comparison - Windows and Linux treat it as string, Mac as bool
        # so we convert string to bool
        if isinstance(is_open, basestring):
            is_open = self.util.str2bool(is_open)
        
        if is_open:
            self.util.msg_log(u'Dialog already opened')
            return
        
        # auf URL testen
        dir_check = self.util.check_dir(self.settings.cache_dir)
        api_url_check = self.util.check_api_url(self.settings.ckan_url)
        if dir_check is False or api_url_check is False:
            dlg = CKANBrowserDialogSettings(self.settings, self.iface, self.iface.mainWindow())
            dlg.show()
            result = dlg.exec_()
            if result != 1:
                return

#         self.util.msg_log('cache_dir: {0}'.format(self.settings.cache_dir))

        try: 
            QSettings().setValue("ckan_browser/isopen", True)
            self.dlg = CKANBrowserDialog(self.settings, self.iface, self.iface.mainWindow())
            
            # show the dialog
            self.dlg.show()
            #self.dlg.open()
            # Run the dialog event loop
            result = self.dlg.exec_()
            # See if OK was pressed
            if result:
                # Do something useful here - delete the line containing pass and
                # substitute with your code.
                pass
        finally: 
            QSettings().setValue("ckan_browser/isopen", False)

    def open_settings(self):
        dlg = CKANBrowserDialogSettings(self.settings, self.iface, self.iface.mainWindow())
        dlg.show()
        dlg.exec_()