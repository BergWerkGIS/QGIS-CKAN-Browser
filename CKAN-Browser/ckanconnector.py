# -*- coding: utf-8 -*-

import json
import os
import sys
import string
import urllib2

from PyQt4.QtCore import *
from qgis.core import *
from qgis.gui import *


# Determine is the new QgsAuthManager is available
try:
    from qgis.core import QgsAuthManager
    from PyQt4.QtNetwork import *

    class RequestsExceptionsTimeout(Exception):
        pass

    class RequestsExceptionsConnectionError(Exception):
        pass

except:
    QgsAuthManager = None
    if sys.platform.startswith('darwin') or os.name == 'nt':
        import request as requests
    else:
        try:
            import requests
        except:
            import request as requests

        class RequestsExceptionsTimeout(requests.exceptions.Timeout):
            pass

        class RequestsExceptionsConnectionError(requests.exceptions.ConnectionError):
            pass


class CkanConnector():
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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'en-US,en;q=0.8,de;q=0.6,de-DE;q=0.4,de-CH;q=0.2',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
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
            for i in xrange(len(groups)):
                groups[i] = u'groups:{0}'.format(groups[i])
            group_filter += '+OR+'.join(groups) + ')'
        self.util.msg_log(u'group_filter: {0}'.format(group_filter))
        if page is None:
            start_query = ''
        else:
            start_query = self.__get_start(page)
        self.util.msg_log(u'start: {0}'.format(start_query))

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

        self.util.msg_log(group_name)
        if page is None:
            start_query = ''
        else:
            start_query = self.__get_start(page)
        self.util.msg_log(u'show_group, start: {0}'.format(start_query))
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
            if not response.ok:
                return False, self.util.tr(u'cc_download_error').format(response.reason), None

            # TODO remove after testing
            # doesn't work headers is object of type 'request.structures.CaseInsensitiveDict'
            # self.util.msg_log(u'{0}'.format(json.dumps(response.headers, indent=2, sort_keys=True)))
            for k, v in response.headers.iteritems():
                self.util.msg_log(u"['{0}']: \t{1}".format(k, v))

            # Content-Disposition:
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec19.html
            # http://www.iana.org/assignments/cont-disp/cont-disp.xhtml
            file_name_from_service = self.__file_name_from_service(
                url
                , response.headers.get('content-disposition')
                , response.headers.get('content-type')
            )
            self.util.msg_log(u'file name from service: {0}'.format(file_name_from_service))
            if file_name_from_service:
                # set new dest_file name
                dest_file = os.path.join(os.path.dirname(dest_file), file_name_from_service)

            self.util.msg_log(u'dest_file: {0}'.format(dest_file))
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

            self.util.msg_log(u'dest_file: {0}'.format(dest_file))

            # if file name has been set from service, set again after above changes for wfs/wm(t)s
            if file_name_from_service:
                # set return value to full path
                file_name_from_service = dest_file

            #chunk_size = 1024
            chunk_size = None
            #http://docs.python-requests.org/en/latest/user/advanced/#chunk-encoded-requests
            if self.__is_chunked(response.headers.get('transfer-encoding')):
                self.util.msg_log('response is chunked')
                chunk_size = None

            with open(dest_file, 'wb') as handle:
                for chunk in response.iter_content(chunk_size):
                    if chunk:
                        handle.write(chunk)

            return True, '', file_name_from_service
        except RequestsExceptionsTimeout as cte:
            #self.util.msg_log(u'{0}\n{1}\n\n\n{2}'.format(cte, dir(cte), cte.message))
            return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        except IOError, e:
            self.util.msg_log("Can't retrieve {0} to {1}: {2}".format(url, dest_file, e))
            return False, self.util.tr(u'cc_download_error').format(e.strerror), None
        except NameError as ne:
            self.util.msg_log(u'{0}'.format(ne))
            return False, ne.message, None
        except:
            return False, self.util.tr(u'cc_download_error').format(sys.exc_info()[0]), None

    def get_file_size(self, url):
        """
        Get Headers for specified url and calculate file size in MB from Content-Length.
        """
        self.util.msg_log(u'Requesting HEAD for: {0}'.format(url))

        try:
            request_head = self._http_call(url, http_method='head')
        except RequestsExceptionsTimeout as cte:
            #self.util.msg_log(u'{0}\n{1}\n\n\n{2}'.format(cte, dir(cte), cte.message))
            return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        except:
            return False, self.util.tr(u'cc_url_error').format(url, sys.exc_info()[1])

        if 'content-length' not in request_head.headers:
            self.util.msg_log(u'No content-length in response header! Returning 0.')
            return True, 0

        content_length = request_head.headers['content-length']
        file_size = int(content_length) / 1000000  # divide to get MB

        self.util.msg_log(u'Content-Length: {0} MB'.format(file_size))

        return True, file_size

    def __is_chunked(self, te):
        if not te:
            return False
        te = te.lower()
        return 'chunked' == te

    def __file_name_from_service(self, url, cd, ct):
        self.util.msg_log(u'Content-Description: {0}\nContent-Type: {1}'.format(cd, ct))

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
            self.util.msg_log('file_name (attachment):' + file_name)
            return file_name

        if 'inline' in cd and 'filename=' in cd:
            file_name = cd.split('filename=')[1]
            file_name = file_name.replace('"', '').replace(';', '')
            self.util.msg_log('file_name (inline):' + file_name)
            if ct:
                ext_ct = ct.split(';')[0].split('/')[1]
                ext_file_name = os.path.splitext(file_name)[1][1:]
                self.util.msg_log(u'ext_ct:{0} ext_file_name:{1}'.format(ext_ct, ext_file_name))
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
            if not response.ok:
                return False, self.util.tr(u'cc_download_error').format(response.reason), None

            # TODO remove after testing
            # doesn't work headers is object of type 'request.structures.CaseInsensitiveDict'
            # self.util.msg_log(u'{0}'.format(json.dumps(response.headers, indent=2, sort_keys=True)))
            for k, v in response.headers.iteritems():
                self.util.msg_log(u"['{0}']: \t{1}".format(k, v))

            # Content-Disposition:
            # http://www.w3.org/Protocols/rfc2616/rfc2616-sec19.html
            # http://www.iana.org/assignments/cont-disp/cont-disp.xhtml
            file_name_from_service = self.__file_name_from_service(
                url
                , response.headers.get('content-disposition')
                , response.headers.get('content-type')
            )
            self.util.msg_log(u'file name from service: {0}'.format(file_name_from_service))
            if file_name_from_service:
                # set new dest_file name
                dest_file = os.path.join(os.path.dirname(dest_file), file_name_from_service)

            self.util.msg_log(u'dest_file: {0}'.format(dest_file))
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

            self.util.msg_log(u'dest_file: {0}'.format(dest_file))

            # if file name has been set from service, set again after above changes for wfs/wm(t)s
            if file_name_from_service:
                # set return value to full path
                file_name_from_service = dest_file

            #chunk_size = 1024
            chunk_size = None
            #http://docs.python-requests.org/en/latest/user/advanced/#chunk-encoded-requests
            if self.__is_chunked(response.headers.get('transfer-encoding')):
                self.util.msg_log('response is chunked')
                chunk_size = None

            with open(dest_file, 'wb') as handle:
                for chunk in response.iter_content(chunk_size):
                    if chunk:
                        handle.write(chunk)

            return True, '', file_name_from_service
        except RequestsExceptionsTimeout as cte:
            #self.util.msg_log(u'{0}\n{1}\n\n\n{2}'.format(cte, dir(cte), cte.message))
            return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        except IOError, e:
            self.util.msg_log("Can't retrieve {0} to {1}: {2}".format(url, dest_file, e))
            return False, self.util.tr(u'cc_download_error').format(e.strerror), None
        except NameError as ne:
            self.util.msg_log(u'{0}'.format(ne))
            return False, ne.message, None
        except:
            return False, self.util.tr(u'cc_download_error').format(sys.exc_info()[0]), None


    def __get_data(self, api, action):
        url = u'{0}{1}'.format(api, action)
        self.util.msg_log(u'api request: {0}'.format(url))
        #pyperclip.copy(url)
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
        except RequestsExceptionsTimeout as cte:
            #self.util.msg_log(u'{0}\n{1}\n\n\n{2}'.format(cte, dir(cte), cte.message))
            return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        except RequestsExceptionsConnectionError as ce:
            self.util.msg_log(u'ConnectionError:{0}'.format(ce))
            return False, ce
        except UnicodeEncodeError as uee:
            self.util.msg_log(u'msg:{0} enc:{1} args:{2} reason:{3}'.format(uee.message, uee.encoding, uee.args, uee.reason))
            return False, self.util.tr(u'cc_api_not_accessible')
        except:
            self.util.msg_log(u'Unerwarteter Fehler beim Request: {0}'.format(sys.exc_info()[0]))
            return False, self.util.tr(u'cc_api_not_accessible')

        if response.status_code != 200:
            return False, self.util.tr(u'cc_server_fault')
        try:
            result = json.loads(response.text)
        except TypeError as te:
            self.util.msg_log(u'Unerwarteter Fehler: {0}'.format(te.message))
            return False, self.util.tr(u'cc_api_not_accessible')
        except AttributeError as ae:
            self.util.msg_log(u'Unerwarteter Fehler: {0}'.format(ae.message))
            return False, self.util.tr(u'cc_api_not_accessible')
        except:
            self.util.msg_log(u'Unerwarteter Fehler: {0}'.format(sys.exc_info()[0]))
            return False, self.util.tr(u'cc_invalid_json')

        if result['success'] is False:
            return False, result['error']['message']
        return True, result['result']


    def _http_call(self, url, **kwargs):
        """
        Uses QgsNetworkAccessManager and fall back to requests library if
        QgsAuthManager is not available.
        """
        method = kwargs.get('http_method', 'get')
        if QgsAuthManager is None:
            # Fall back to requests lib
            return getattr(requests, method)(url, **kwargs)

        headers = kwargs.get('headers', {})
        # This fixes a wierd error with compressed content nob being correctly
        # inflated.
        # If you set the header on the QNetworkRequest you are basically telling
        # QNetworkAccessManager "I know what I'm doing, please don't do any content
        # encoding processing".
        # See: https://bugs.webkit.org/show_bug.cgi?id=63696#c1
        try:
            del headers['Accept-Encoding']
        except KeyError:
            pass
        # Avoid double quoting form QUrl
        url = urllib2.unquote(url)

        self.util.msg_log(u'http_call request: {0}'.format(url))

        class Response():
            status_code = 200
            status_message = 'OK'
            text = ''
            ok = True
            headers = {}
            reason = ''

            def iter_content(self, _):
                return [self.text]

        self.http_call_result = Response()
        url = self.util.remove_newline(url)
        req = QNetworkRequest()
        req.setUrl(QUrl(url))
        for k, v in headers.items():
            self.util.msg_log("%s: %s" % (k, v))
            req.setRawHeader(k, v)
        if self.authcfg:
            QgsAuthManager.instance().updateNetworkRequest(req, self.authcfg)
        if self.reply is not None and self.reply.isRunning():
            self.reply.close()
        func = getattr(QgsNetworkAccessManager.instance(), method)
        # Calling the server ...
        # Let's log the whole call for debugging purposes:
        if self.settings.debug:
            self.util.msg_log("Sending %s request to %s" % (method.upper(), req.url().toString()))
            headers = {str(h): str(req.rawHeader(h)) for h in req.rawHeaderList()}
            for k, v in headers.items():
                self.util.msg_log("%s: %s" % (k, v))
        self.reply = func(req)
        if self.authcfg:
            self.util.msg_log("update reply w/ authcfg: {0}".format(self.authcfg))
            QgsAuthManager.instance().updateNetworkReply(self.reply, self.authcfg)

        self.reply.finished.connect(self.replyFinished)

        # Call and block
        self.el = QEventLoop()
        self.reply.finished.connect(self.el.quit)

        # Catch all exceptions (and clean up requests)
        try:
            self.el.exec_()
            # Let's log the whole response for debugging purposes:
            if self.settings.debug:
                self.util.msg_log("Got response %s %s from %s" % \
                                  (self.http_call_result.status_code,
                                   self.http_call_result.status_message,
                                   self.reply.url().toString()))
                headers = {str(h): str(self.reply.rawHeader(h)) for h in self.reply.rawHeaderList()}
                for k, v in headers.items():
                    self.util.msg_log("%s: %s" % (k, v))
                if len(self.http_call_result.text) < 1024:
                    self.util.msg_log("Payload :\n%s" % self.http_call_result.text)
                else:
                    self.util.msg_log("Payload is > 1 KB ...")
        except Exception, e:
            raise e
        finally:
            self.reply.close()
            self.util.msg_log("Deleting reply ...")
            self.reply.deleteLater()
            self.reply = None
        return self.http_call_result

    @pyqtSlot()
    def replyFinished(self):
        err = self.reply.error()
        httpStatus = self.reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        httpStatusMessage = self.reply.attribute(QNetworkRequest.HttpReasonPhraseAttribute)
        self.http_call_result.status_code = httpStatus
        self.http_call_result.status_message = httpStatusMessage
        for k, v in self.reply.rawHeaderPairs():
            self.http_call_result.headers[str(k)] = str(v)
            self.http_call_result.headers[str(k).lower()] = str(v)
        if err != QNetworkReply.NoError:
            self.http_call_result.ok = False
            msg = "Network error #{0}: {1}".format(
                self.reply.error(), self.reply.errorString())
            self.http_call_result.reason = msg
            self.util.msg_log(msg)
            if err == QNetworkReply.TimeoutError:
                raise RequestsExceptionsTimeout(msg)
            if err == QNetworkReply.ConnectionRefusedError:
                raise RequestsExceptionsConnectionError(msg)
            else:
                raise Exception(msg)
        else:
            self.http_call_result.text = str(self.reply.readAll())
            self.http_call_result.ok = True


    def __get_start(self, page):
        start = self.limit * page - self.limit
        return u'&start={0}'.format(start)

    def _validate_ckan_url(self, ckan_url):
        """Validate the CKAN API URL - check for trailing slash and correct API Version"""
        if not ckan_url.endswith("/"):
            ckan_url += "/"

        if not ckan_url.endswith("3/"):  # was bei neuen APIS > 3?
            self.util.msg_log(u'Falsche API-Version: {0}'.format(ckan_url))
#             self.util.dlg_warning(self.util.tr(u"cc_wrong_api"))
            return False, self.util.tr(u"cc_wrong_api")

        return True, ckan_url
