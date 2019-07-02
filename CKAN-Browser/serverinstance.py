from qgis.core import QgsStringUtils


class ServerInstance:

    def __init__(self, title, description, api_url, selected=False, custom_entry=False):
        self.__title = title.strip()
        self.description = description.replace('\n', ' ').strip()
        new_line = '' if not self.__title or self.__title.isspace() or not self.description or self.description.isspace() else '\n'
        self.title = u'{}{}{}'.format(self.__title, new_line, self.description)
        self.api_url = api_url
        self.selected = selected
        self.last_search_result = 0

    def search(self, search_term):
        if not search_term or search_term.isspace():
            self.last_search_result = 100
            return 100

        ret_val = 0
        # TODO: tokenize search term
        # se_term = QgsStringUtils.soundex(search_term)
        for token in self.title.split():
            if QgsStringUtils.levenshteinDistance(token, search_term, False) < 3:
                ret_val += 1
            # se_token = QgsStringUtils.soundex(token)
            # if QgsStringUtils.levenshteinDistance(se_term, se_token) < 2:
            #    ret_val += 1
        self.last_search_result = ret_val
        return ret_val
