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

from PyQt5 import QtGui, uic
from PyQt5.QtWidgets import QDialog
from .util import Util

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(
        os.path.dirname(__file__),
        'ckan_browser_dialog_disclaimer.ui'
    )
)


class CKANBrowserDialogDisclaimer(QDialog, FORM_CLASS):
    def __init__(self, settings, parent=None):
        """Constructor."""
        super(CKANBrowserDialogDisclaimer, self).__init__(parent)
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
        
        logo_path = self.util.resolve(u'ckan_logo_big.png')
        self.IDC_lblLogo.setPixmap(QtGui.QPixmap(logo_path))
        self.IDC_brInfo.setOpenExternalLinks(True)
        self.IDC_brInfo.setHtml(self.util.tr('py_disc_info_html'))
