# -*- coding: utf-8 -*-

import inspect
import json
import os
import sys
import string
import traceback
#from urllib3

from PyQt5.QtCore import *
from PyQt5 import QtNetwork
from qgis.core import QgsNetworkAccessManager


from urllib.parse import unquote
from .pyperclip import copy


from qgis.core import QgsAuthManager
from PyQt5.QtNetwork import *


class RequestsException(Exception):
    pass


class RequestsExceptionTimeout(RequestsException):
    pass


class RequestsExceptionConnectionError(RequestsException):
    pass


class RequestsExceptionUserAbort(RequestsException):
    pass


class CkanConnector:
    """CKAN Connector"""

    def __init__(self, settings, util):
        self.settings = settings
        self.util = util
        self.api = self.settings.ckan_url
        self.cache = self.settings.cache_dir
        self.limit = self.settings.results_limit
        self.authcfg = self.settings.authcfg
        #self.sort = 'name asc, title asc'
        self.sort = 'name asc'
        self.reply = None
        self.ua_chrome = {
            b'Accept': b'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            # DON'T use: haven't found a way to tell QNetworkRequest to decompress on the fly
            # although it should automatically when this header is present
            # https://code.qt.io/cgit/qt/qtbase.git/tree/src/network/access/qhttpnetworkconnection.cpp?h=5.11#n299
            #b'Accept-Encoding': b'gzip, deflate',
            b'Accept-Language': b'en-US,en;q=0.8,de;q=0.6,de-DE;q=0.4,de-CH;q=0.2',
            b'User-Agent': b'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
        }

    def get_groups(self):
        # return self.__get_data(self.api, 'group_list?all_fields=true')
        ok, result = self._validate_ckan_url(self.api)

        if not ok:
            return ok, result

        return self.__get_data(result, 'action/group_list?all_fields=true')

    def test_groups(self, test_path):
        ok, result = self._validate_ckan_url(test_path)

        if not ok:
            return ok,result

        return self.__get_data(result, 'action/group_list?all_fields=true')

    def package_search(self, text, groups=None, page=None):
        ok, result = self._validate_ckan_url(self.api)

        if not ok:
            return ok, result

        if groups is None:
            group_filter = ''
        else:
            group_filter = '&fq=('
            for i in range(len(groups)):
                groups[i] = u'groups:{0}'.format(groups[i])
            group_filter += '+OR+'.join(groups) + ')'
        self.util.msg_log_debug(u'group_filter: {0}'.format(group_filter))
        if page is None:
            start_query = ''
        else:
            start_query = self.__get_start(page)
        self.util.msg_log_debug(u'start: {0}'.format(start_query))

        # autocomplete http://ckan.data.ktn.gv.at/api/3/action/package_autocomplete?q=wasser
        # return self.__get_data(u'package_search?q={0}&rows=10'.format(text))
        # limit für ausgabe: http://demo.ckan.org/api/3/action/package_search?q=spending&rows=10
        # mehrere begriffe: http://demo.ckan.org/api/3/action/term_translation_show?terms=russian&terms=romantic%20novel
        return self.__get_data(
                result,
                u'action/package_search?q={0}{1}&sort={2}&rows={3}{4}'.format(
                    text,
                    group_filter,
                    self.sort,
                    self.limit,
                    start_query
                )
        )

    def show_group(self, group_name, page=None):
        ok, result = self._validate_ckan_url(self.api)

        if not ok:
            return ok,result

        self.util.msg_log_debug(group_name)
        if page is None:
            start_query = ''
        else:
            start_query = self.__get_start(page)
        self.util.msg_log_debug(u'show_group, start: {0}'.format(start_query))
        #return self.__get_data(
        #    result, u'action/group_package_show?id={0}&rows={1}{2}'.format(
        #        group_name,
        #        #1000,
        #        self.limit,
        #        start_query
        #    )
        return self.__get_data(
            result, u'action/package_search?q=&fq=(groups:{0})&sort={1}&rows={2}{3}'.format(
                group_name,
                self.sort,
                self.limit,
                start_query
            )
        )

    def get_file_size(self, url):
        """
        Get Headers for specified url and calculate file size in MB from Content-Length.
        """
        self.util.msg_log_debug(u'Requesting HEAD for: {0}'.format(url))

        try:
            request_head = self._http_call(url, http_method='head')

            self.util.msg_log_error(u'response:\n{}'.format(request_head))

        #except RequestsExceptionsTimeout as cte:
            #self.util.msg_log(u'{0}\n{1}\n\n\n{2}'.format(cte, dir(cte), cte.message))
            #return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        except:
            return False, self.util.tr(u'cc_url_error').format(url, sys.exc_info()[1])

        if 'content-length' not in request_head.headers:
            self.util.msg_log_debug(u'No content-length in response header! Returning 0.')
            return True, 0

        content_length = request_head.headers['content-length']
        file_size = int(content_length) / 1000000  # divide to get MB

        self.util.msg_log_debug(u'Content-Length: {0} MB'.format(file_size))

        return True, file_size

    def __is_chunked(self, te):
        if not te:
            return False
        te = te.lower()
        return 'chunked' == te

    def __file_name_from_service(self, url, cd, ct):
        self.util.msg_log_debug(u'Content-Description: {0}\nContent-Type: {1}'.format(cd, ct))

        url = url.lower() if url else None
        cd = cd.lower() if cd else None
        ct = ct.lower() if ct else None

        if not cd:
            ## disabled: Bildungsstandorte Vorarlberg, should be shape
            ## but if an error xml
            #if url:
            #    if 'outputformat=shape-zip' in url:
            #        return 'zipped-shape-no-name.zip'
            return None

        if 'attachment' in cd and 'filename=' in cd:
            file_name = cd.split('filename=')[1]
            file_name = file_name.replace('"', '').replace(';', '')
            self.util.msg_log_debug('file_name (attachment):' + file_name)
            return file_name

        if 'inline' in cd and 'filename=' in cd:
            file_name = cd.split('filename=')[1]
            file_name = file_name.replace('"', '').replace(';', '')
            self.util.msg_log_debug('file_name (inline):' + file_name)
            if ct:
                ext_ct = ct.split(';')[0].split('/')[1]
                ext_file_name = os.path.splitext(file_name)[1][1:]
                self.util.msg_log_debug(u'ext_ct:{0} ext_file_name:{1}'.format(ext_ct, ext_file_name))
                if ext_file_name not in ext_ct:
                    file_name += '.' + ext_ct
            return file_name

        return None

    def download_resource(self, url, resource_format, dest_file, delete):
        try:
#             if resource_format is not None:
#                 if resource_format.lower() == 'georss':
#                     dest_file += '.xml'
            if delete is True:
                os.remove(dest_file)
            #urls might have line breaks
            url = self.util.remove_newline(url)
            response = self._http_call(
                url
                , headers=self.ua_chrome
                , verify=False
                , stream=True
                , proxies=self.settings.get_proxies()[1]
                , timeout=self.settings.request_timeout
            )

            self.util.msg_log_error(
                u'response:\nex:{0}\nhdr:{1}\nok:{2}\nreason:{3}\nstcode:{4}\nstmsg:{5}\ncontent:{6}'
                .format(
                    response.exception,
                    response.headers,
                    response.ok,
                    response.reason,
                    response.status_code,
                    response.status_message,
                    response.text[:255]
                )
            )

            if not response.ok:
                return False, self.util.tr(u'cc_download_error').format(response.reason), None

            # Content-Disposition:
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec19.html
            # http://www.iana.org/assignments/cont-disp/cont-disp.xhtml
            file_name_from_service = self.__file_name_from_service(
                url
                , response.headers.get('content-disposition')
                , response.headers.get('content-type')
            )
            self.util.msg_log_debug(u'file name from service: {0}'.format(file_name_from_service))
            if file_name_from_service:
                # set new dest_file name
                dest_file = os.path.join(os.path.dirname(dest_file), file_name_from_service)

            self.util.msg_log_debug(u'dest_file: {0}'.format(dest_file))
            # hack for WFS/WM(T)S Services, that don't specify the format as wms, wmts or wfs
            url_low = url.lower()
            if 'wfs' in url_low and 'getcapabilities' in url_low and False is dest_file.endswith('.wfs'):
                if string.find(dest_file, '?') > -1: dest_file = dest_file[:string.find(dest_file, '?')]
                dest_file += '.wfs'
            if 'wmts' in url_low and 'getcapabilities' in url_low and False is dest_file.endswith('.wmts'):
                if string.find(dest_file, '?') > -1: dest_file = dest_file[:string.find(dest_file, '?')]
                dest_file += '.wmts'
            # we use extension wmts for wms too
            if 'wms' in url_low and 'getcapabilities' in url_low and False is dest_file.endswith('.wmts'):
                if string.find(dest_file, '?') > -1: dest_file = dest_file[:string.find(dest_file, '?')]
                dest_file += '.wmts'

            self.util.msg_log_debug(u'dest_file: {0}'.format(dest_file))

            # if file name has been set from service, set again after above changes for wfs/wm(t)s
            if file_name_from_service:
                # set return value to full path
                file_name_from_service = dest_file

            #chunk_size = 1024
            chunk_size = None
            #http://docs.python-requests.org/en/latest/user/advanced/#chunk-encoded-requests
            if self.__is_chunked(response.headers.get('transfer-encoding')):
                self.util.msg_log_debug('response is chunked')
                chunk_size = None

            with open(dest_file, 'wb') as handle:
                for chunk in response.iter_content(chunk_size):
                    if chunk:
                        handle.write(chunk)

            return True, '', file_name_from_service
        #except RequestsExceptionsTimeout as cte:
            #self.util.msg_log(u'{0}\n{1}\n\n\n{2}'.format(cte, dir(cte), cte.message))
            #return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        except IOError as e:
            self.util.msg_log_debug("Can't retrieve {0} to {1}: {2}".format(url, dest_file, e))
            return False, self.util.tr(u'cc_download_error').format(e.strerror), None
        except NameError as ne:
            self.util.msg_log_debug(u'{0}'.format(ne))
            return False, ne.message, None
        except:
            self.util.msg_log_last_exception()
            return False, self.util.tr(u'cc_download_error').format(sys.exc_info()[0]), None

    def __get_data(self, api, action):
        url = u'{0}{1}'.format(api, action)
        self.util.msg_log_debug(u'api request: {0}'.format(url))
        copy(url)
        # url = u'{0}{1}'.format(self.api, unicodedata.normalize('NFKD', action))
        try:
            url = self.util.remove_newline(url)
            response = self._http_call(
                url
                , headers=self.ua_chrome
                , verify=False
                , proxies=self.settings.get_proxies()[1]
                , timeout=self.settings.request_timeout
            )

            self.util.msg_log_error(u'response:\n{}'.format(response))

        #except RequestsExceptionsTimeout as cte:
            #self.util.msg_log_error(u'connection timeout for: {0}'.format(url))
            #return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        #except RequestsExceptionsConnectionError as ce:
            #self.util.msg_log_error(u'ConnectionError:{0}'.format(ce))
            #return False, ce
        except UnicodeEncodeError as uee:
            self.util.msg_log_error(u'msg:{0} enc:{1} args:{2} reason:{3}'.format(uee.message, uee.encoding, uee.args, uee.reason))
            return False, self.util.tr(u'cc_api_not_accessible')
        except:
            self.util.msg_log_error(u'unexpected error during request: {0}'.format(sys.exc_info()[0]))
            self.util.msg_log_last_exception()
            return False, self.util.tr(u'cc_api_not_accessible')

        if response.status_code != 200:
            return False, self.util.tr(u'cc_server_fault')

        # decode QByteArray
        try:
            json_txt = response.text.data().decode()
            self.util.msg_log_debug(u'resp_msg (decoded):\n{} .......'.format(json_txt[:255]))
            result = json.loads(json_txt)
        except TypeError as te:
            self.util.msg_log_error(u'unexpected TypeError: {0}'.format(te.message))
            return False, self.util.tr(u'cc_api_not_accessible')
        except AttributeError as ae:
            self.util.msg_log_error(u'unexpected AttributeError: {0}'.format(ae.message))
            return False, self.util.tr(u'cc_api_not_accessible')
        except:
            self.util.msg_log_error(u'unexpected error during request or parsing of response:')
            self.util.msg_log_last_exception()
            return False, self.util.tr(u'cc_invalid_json')

        if result['success'] is False:
            return False, result['error']['message']
        return True, result['result']

    def _http_call(self, url, **kwargs):
        """
        Uses QgsNetworkAccessManager and fall back to requests library if
        QgsAuthManager is not available.
        """
        self.util.msg_log_debug('trying to use "http_call"')
        method = kwargs.get('http_method', 'get')

        headers = kwargs.get('headers', {})
        # This fixes a weird error with compressed content not being correctly
        # inflated.
        # If you set the header on the QNetworkRequest you are basically telling
        # QNetworkAccessManager "I know what I'm doing, please don't do any content
        # encoding processing".
        # See: https://bugs.webkit.org/show_bug.cgi?id=63696#c1
        try:
            del headers['Accept-Encoding']
        except KeyError as ke:
            self.util.msg_log_debug(u'{}'.format(ke))
            pass

        # Avoid double quoting form QUrl
        url = unquote(url)

        self.util.msg_log_debug(u'http_call request: {0}'.format(url))

        class Response:
            status_code = 200
            status_message = 'OK'
            text = ''
            ok = True
            headers = {}
            reason = ''
            exception = None

            def iter_content(self, _):
                return [self.text]

        self.http_call_result = Response()
        url = self.util.remove_newline(url)

        req = QNetworkRequest()
        req.setUrl(QUrl(url))

        for k, v in headers.items():
            self.util.msg_log_debug("%s: %s" % (k, v))
            try:
                req.setRawHeader(k, v)
            except:
                self.util.msg_log_error(u'FAILED to set header: {} => {}'.format(k, v))
                self.util.msg_log_last_exception()
        if self.authcfg:
            self.util.msg_log_debug(u'before updateNetworkRequest')
            QgsAuthManager.instance().updateNetworkRequest(req, self.authcfg)
            self.util.msg_log_debug(u'before updateNetworkRequest')

        if self.reply is not None and self.reply.isRunning():
            self.reply.close()

        self.util.msg_log_debug(u'getting QgsNetworkAccessManager.instance()')
        #func = getattr(QgsNetworkAccessManager.instance(), method)
        #func = QgsNetworkAccessManager().get(req)




        #manager = QNetworkAccessManager()
        #event = QEventLoop()
        #response = manager.get(QNetworkRequest(QUrl(url)))
        #response.downloadProgress.connect(self.download_progress)
        #response.finished.connect(event.quit)
        #event.exec()
        #response_msg = response.readAll()
        ##response_msg = str(response_msg)
        #response_msg = str(response_msg, encoding='utf-8')
        ##response_msg = response_msg.decode('utf-8')
        #response.deleteLater()
        #self.util.msg_log_debug(u'response message:\n{} ...'.format(response_msg[:255]))
        #self.http_call_result.text = response_msg  # in Python3 all strings are unicode, so QString is not defined
        #return self.http_call_result



        # Calling the server ...
        self.util.msg_log_debug('before self.reply = func(req)')
        #self.reply = func(req)
        self.reply = QgsNetworkAccessManager.instance().get(req)
        #self.reply = QNetworkAccessManager().get(req)
        self.util.msg_log_debug('after self.reply = func(req)')

        # Let's log the whole call for debugging purposes:
        if self.settings.debug:
            self.util.msg_log_debug("\nSending %s request to %s" % (method.upper(), req.url().toString()))
            headers = {str(h): str(req.rawHeader(h)) for h in req.rawHeaderList()}
            for k, v in headers.items():
                try:
                    self.util.msg_log_debug("%s: %s" % (k, v))
                except:
                    self.util.msg_log_debug('error logging headers')

        if self.authcfg:
            self.util.msg_log_debug("update reply w/ authcfg: {0}".format(self.authcfg))
            QgsAuthManager.instance().updateNetworkReply(self.reply, self.authcfg)

        self.util.msg_log_debug('before connecting to events')

        # connect downloadProgress event
        try:
            self.reply.downloadProgress.connect(self.download_progress)
            #pass
        except:
            self.util.msg_log_error('error connecting "downloadProgress" event')
            self.util.msg_log_last_exception()

        # connect reply finished event
        try:
            self.reply.finished.connect(self.reply_finished)
            #pass
        except:
            self.util.msg_log_error('error connecting reply "finished" progress event')
            self.util.msg_log_last_exception()
        self.util.msg_log_debug('after connecting to events')

        # Call and block
        self.event_loop = QEventLoop()
        try:
            self.reply.finished.connect(self.event_loop.quit)
        except:
            self.util.msg_log_error('error connecting reply "finished" progress event to event loop quit')
            self.util.msg_log_last_exception()

        # Catch all exceptions (and clean up requests)
        self.event_loop.exec()

        # Let's log the whole response for debugging purposes:
        if self.settings.debug:
            self.util.msg_log_debug(
                u'\nGot response [{}/{}] ({} bytes) from:\n{}'.format(
                    self.http_call_result.status_code,
                    self.http_call_result.status_message,
                    len(self.http_call_result.text),
                    self.reply.url().toString()
                )
            )
            headers = {str(h): str(self.reply.rawHeader(h)) for h in self.reply.rawHeaderList()}
            for k, v in headers.items():
                self.util.msg_log_debug("%s: %s" % (k, v))
            self.util.msg_log_debug("Payload :\n%s ......" % self.http_call_result.text[:255])
        self.reply.close()
        self.util.msg_log_debug("Deleting reply ...")
        try:
            self.reply.deleteLater()
        except:
            self.util.msg_log_last_exception()
        self.reply = None
        if self.http_call_result.exception is not None:
            raise self.http_call_result.exception
        return self.http_call_result

    def download_progress(self, bytes_received, bytes_total):
        self.util.msg_log_debug(
            u'downloadProgress {:.1f} of {:.1f} MB" '
            .format(bytes_received / (1024 * 1024), bytes_total / (1024 * 1024))
        )

    def reply_finished(self):
        self.util.msg_log_debug('------- reply_finished')
        try:
            err = self.reply.error()
            httpStatus = self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            httpStatusMessage = self.reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
            self.http_call_result.status_code = httpStatus
            self.http_call_result.status_message = httpStatusMessage
            for k, v in self.reply.rawHeaderPairs():
                self.http_call_result.headers[str(k)] = str(v)
                self.http_call_result.headers[str(k).lower()] = str(v)
            if err != QNetworkReply.NoError:
                self.util.msg_log_debug('!QNetworkReply.NoError')
                self.http_call_result.ok = False
                msg = "Network error #{0}: {1}".format(
                    self.reply.error(), self.reply.errorString())
                self.http_call_result.reason = msg
                self.util.msg_log_debug(msg)
                if err == QNetworkReply.TimeoutError:
                    self.http_call_result.exception = RequestsExceptionTimeout(msg)
                if err == QNetworkReply.ConnectionRefusedError:
                    self.http_call_result.exception = RequestsExceptionConnectionError(msg)
                else:
                    self.http_call_result.exception = Exception(msg)
            else:
                self.util.msg_log_debug('QNetworkReply.NoError')
                self.http_call_result.text = self.reply.readAll()
                self.http_call_result.ok = True
        except:
            self.util.msg_log_error(u'unexpected error in {}'.format(inspect.stack()[0][3]))
            self.util.msg_log_last_exception()

    def __get_start(self, page):
        start = self.limit * page - self.limit
        return u'&start={0}'.format(start)

    def _validate_ckan_url(self, ckan_url):
        """Validate the CKAN API URL - check for trailing slash and correct API Version"""
        if not ckan_url.endswith("/"):
            ckan_url += "/"

        if not ckan_url.endswith("3/"):  # was bei neuen APIS > 3?
            self.util.msg_log_debug(u'unsupported API version: {0}'.format(ckan_url))
#             self.util.dlg_warning(self.util.tr(u"cc_wrong_api"))
            return False, self.util.tr(u"cc_wrong_api")

        return True, ckan_url
