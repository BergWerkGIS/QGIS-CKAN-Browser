# -*- coding: utf-8 -*-

import json
import os
import sys
import string


from .httpcall import HttpCall
from .httpcall import RequestsException
from .httpcall import RequestsExceptionTimeout
from .httpcall import RequestsExceptionConnectionError
from .httpcall import RequestsExceptionUserAbort
from .pyperclip import copy


class CkanConnector:
    """CKAN Connector"""

    def __init__(self, settings, util):
        self.settings = settings
        self.settings.load()
        self.util = util
        #self.api = self.settings.ckan_url
        #self.cache = self.settings.cache_dir
        #self.limit = self.settings.results_limit
        #self.auth_cfg = self.settings.authcfg
        # self.sort = 'name asc, title asc'
        self.sort = 'name asc'
        self.mb_downloaded = 0
        self.ua_chrome = {
            b'Accept': b'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            # DON'T use: haven't found a way to tell QNetworkRequest to decompress on the fly
            # although it should automatically when this header is present
            # https://code.qt.io/cgit/qt/qtbase.git/tree/src/network/access/qhttpnetworkconnection.cpp?h=5.11#n299
            b'Accept-Encoding': b'gzip, deflate',
            b'Accept-Language': b'en-US,en;q=0.8,de;q=0.6,de-DE;q=0.4,de-CH;q=0.2',
            b'User-Agent': b'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
        }

    def get_groups(self):
        # return self.__get_data(self.api, 'group_list?all_fields=true')
        ok, result = self._validate_ckan_url(self.settings.ckan_url)

        if not ok:
            return ok, result

        return self.__get_data(result, 'action/group_list?all_fields=true')

    def test_groups(self, test_path):
        ok, result = self._validate_ckan_url(test_path)

        if not ok:
            return ok, result

        return self.__get_data(result, 'action/group_list?all_fields=true')

    def package_search(self, text, groups=None, page=None):
        ok, result = self._validate_ckan_url(self.settings.ckan_url)

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
        # limit results: http://demo.ckan.org/api/3/action/package_search?q=spending&rows=10
        # several terms: http://demo.ckan.org/api/3/action/term_translation_show?terms=russian&terms=romantic%20novel
        return self.__get_data(
                result,
                u'action/package_search?q={0}{1}&sort={2}&rows={3}{4}'.format(
                    text,
                    group_filter,
                    self.sort,
                    self.settings.results_limit,
                    start_query
                )
        )

    def show_group(self, group_name, page=None):
        ok, result = self._validate_ckan_url(self.settings.ckan_url)

        if not ok:
            return ok, result

        self.util.msg_log_debug(group_name)
        if page is None:
            start_query = ''
        else:
            start_query = self.__get_start(page)

        self.util.msg_log_debug(u'show_group, start: {0}'.format(start_query))

        return self.__get_data(
            result, u'action/package_search?q=&fq=(groups:{0})&sort={1}&rows={2}{3}'.format(
                group_name,
                self.sort,
                self.settings.results_limit,
                start_query
            )
        )

    def get_file_size(self, url):
        """
        Get Headers for specified url and calculate file size in MB from Content-Length.
        """
        self.util.msg_log_debug(u'Requesting HEAD for: {0}'.format(url))

        try:
            http_call = HttpCall(self.settings, self.util)
            request_head = http_call.execute_request(url, http_method='head')

            self.util.msg_log_debug(
                u'get_file_size response:\nex:{0}\nhdr:{1}\nok:{2}\nreason:{3}\nstcode:{4}\nstmsg:{5}\ncontent:{6}'
                .format(
                    request_head.exception,
                    request_head.headers,
                    request_head.ok,
                    request_head.reason,
                    request_head.status_code,
                    request_head.status_message,
                    request_head.text[:255]
                )
            )

            if not request_head.ok:
                the_exception = request_head.exception if request_head.exception else Exception(self.util.tr(u'cc_url_error'))
                return False, self.util.tr(u'cc_url_error'), the_exception

        except RequestsExceptionTimeout as cte:
            self.util.msg_log(u'{0}\n{1}\n\n\n{2}'.format(cte, dir(cte), cte))
            return False, self.util.tr(u'cc_connection_timeout').format(cte), cte
        except:
            return False, self.util.tr(u'cc_url_error').format(url, sys.exc_info()[1]), Exception(self.util.tr(u'cc_url_error'))

        # HACK
        # headers and their values are returned as strings like this:
        # "b'95140771'"
        # how to fix this properly???
        if "b'Content-Length'" not in request_head.headers:
            self.util.msg_log_debug(u'No content-length in response header! Returning 0.')
            for h in request_head.headers:
                self.util.msg_log_debug(u'{}'.format(h))
            return True, 0, None

        # HACK
        # headers are returned as strings like this: "b'95140771'"
        # how to fix this properly???
        #content_length = request_head.headers[b'content-length']
        content_length = request_head.headers["b'Content-Length'"].replace('b', '').replace("'", '')
        file_size = int(content_length) / 1000000  # divide to get MB

        self.util.msg_log_debug(u'Content-Length: {0} MB'.format(file_size))

        return True, file_size, None

    def __is_chunked(self, te):
        if not te:
            return False
        te = te.lower()
        return 'chunked' == te

    def __file_name_from_service(self, url, cd, ct):
        self.util.msg_log_debug(
            u'__file_name_from_service:\nurl: {}\nContent-Description: {}\nContent-Type: {}'
            .format(url, cd, ct)
        )

        cd = cd.lower() if cd else None
        ct = ct.lower() if ct else None

        if not cd:
            # return None
            # try to get something out of the url
            # and get rid of '?' and '&'
            file_name = url[url.rfind("/") + 1:]
            if file_name.find('?') > -1:
                file_name = file_name[:file_name.find('?')]
            if file_name.find('&') > -1:
                file_name = file_name[:file_name.find('&')]
            return file_name

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

            # urls might have line breaks
            url = self.util.remove_newline(url)

            http_call = HttpCall(self.settings, self.util)
            response = http_call.execute_request(
                url
                , headers=self.ua_chrome
                , verify=False
                , stream=True
                , proxies=self.settings.get_proxies()[1]
                , timeout=self.settings.request_timeout
            )

            self.util.msg_log_debug(
                u'download_resource response:\nex:{0}\nhdr:{1}\nok:{2}\nreason:{3}\nstcode:{4}\nstmsg:{5}\ncontent:{6}'
                .format(
                    response.exception,
                    '\n'.join([u'{}: {}'.format(hdr, response.headers[hdr]) for hdr in response.headers]),
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
                , response.headers.get('Content-Disposition')
                , response.headers.get('Content-Type')
            )
            self.util.msg_log_debug(u'file name from service: {0}'.format(file_name_from_service))
            if file_name_from_service:
                # set new dest_file name
                dest_file = os.path.join(os.path.dirname(dest_file), file_name_from_service)

            self.util.msg_log_debug(u'dest_file: {0}'.format(dest_file))

            # hack for WFS/WM(T)S Services, that don't specify the format as wms, wmts or wfs
            url_low = url.lower()
            self.util.msg_log_debug(u'url.lower(): {0}'.format(url.lower()))

            if 'wfs' in url_low and 'getcapabilities' in url_low and not dest_file.endswith('.wfs'):
                if dest_file.find('?') > -1:
                    dest_file = dest_file[:dest_file.find('?')]
                self.util.msg_log_debug('wfs: adding ".wfs"')
                dest_file += '.wfs'
            if 'wmts' in url_low and 'getcapabilities' in url_low and not dest_file.endswith('.wmts'):
                if dest_file.find('?') > -1:
                    dest_file = dest_file[:dest_file.find('?')]
                self.util.msg_log_debug('wmts: adding ".wmts"')
                dest_file += '.wmts'
            # !!!!! we use extension wmts for wms too !!!!
            if 'wms' in url_low and 'getcapabilities' in url_low and not dest_file.endswith('.wmts'):
                if dest_file.find('?') > -1:
                    dest_file = dest_file[:dest_file.find('?')]
                self.util.msg_log_debug('wms: adding ".wmts"')
                dest_file += '.wmts'

            # in case some query parameters still slipped through, once again: check for '?'
            self.util.msg_log_debug(u'dest_file before final removal of "?" and "&": {0}'.format(dest_file))
            file_name_without_extension, file_extension = os.path.splitext(dest_file)
            self.util.msg_log_debug(u'file name:{}\n extension:{}'.format(file_name_without_extension, file_extension))
            if dest_file.find('?') > -1:
                dest_file = dest_file[:dest_file.find('?')] + file_extension
            if dest_file.find('&') > -1:
                dest_file = dest_file[:dest_file.find('&')] + file_extension

            self.util.msg_log_debug(u'final dest_file: {0}'.format(dest_file))

            # if file name has been set from service, set again after above changes for wfs/wm(t)s
            if file_name_from_service:
                # set return value to full path
                file_name_from_service = dest_file

            #chunk_size = 1024
            chunk_size = None
            #http://docs.python-requests.org/en/latest/user/advanced/#chunk-encoded-requests
            if self.__is_chunked(response.headers.get(b'Transfer-Encoding')):
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
            self.util.msg_log_debug("download_resource, Can't retrieve {0} to {1}: {2}".format(url, dest_file, e))
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
            http_call = HttpCall(self.settings, self.util)
            response = http_call.execute_request(
                url
                , headers=self.ua_chrome
                , verify=False
                , proxies=self.settings.get_proxies()[1]
                , timeout=self.settings.request_timeout
            )

            self.util.msg_log_debug(
                u'__get_data response:\nex:{0}\nhdr:{1}\nok:{2}\nreason:{3}\nstcode:{4}\nstmsg:{5}\ncontent:{6}'
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
                return False, self.util.tr(u'cc_api_not_accessible').format(response.reason)

        except RequestsExceptionTimeout as cte:
            self.util.msg_log_error(u'connection timeout for: {0}'.format(url))
            return False, self.util.tr(u'cc_connection_timeout').format(cte.message)
        except RequestsExceptionConnectionError as ce:
            self.util.msg_log_error(u'ConnectionError:{0}'.format(ce))
            return False, ce
        except UnicodeEncodeError as uee:
            self.util.msg_log_error(u'msg:{0} enc:{1} args:{2} reason:{3}'.format(uee.message, uee.encoding, uee.args, uee.reason))
            return False, self.util.tr(u'cc_api_not_accessible')
        #except:
        #    self.util.msg_log_error(u'unexpected error during request: {0}'.format(sys.exc_info()[0]))
        #    self.util.msg_log_last_exception()
        #    return False, self.util.tr(u'cc_api_not_accessible')

        if response.status_code != 200:
            return False, self.util.tr(u'cc_server_fault')

        # decode QByteArray
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

        if result['success'] is False:
            return False, result['error']['message']
        return True, result['result']

    def __get_start(self, page):
        start = self.settings.results_limit * page - self.settings.results_limit
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
