from qgis.core import QgsStringUtils


class ServerInstance:

    def __init__(self, title, description, url, api_url, selected=False, custom_entry=False):
        self.__title = title.strip()
        self.description = description.replace('\n', ' ').strip()
        new_line = '' if not self.__title or self.__title.isspace() or not self.description or self.description.isspace() else '\n'
        self.short_title = title
        self.title = u'{}{}{}'.format(self.__title, new_line, self.description)
        self.url = url
        self.api_url = api_url
        self.selected = selected
        self.is_custom = custom_entry
        self.settings_key = self.short_title + self.url
        self.last_search_result = 0

    def __repr__(self):
        return f'{self.api_url} {self.__title!r}, {self.description!r}'

    def search(self, search_term):
        if not search_term or search_term.isspace():
            self.last_search_result = 100
            return 100

        ret_val = 0

        # give more weight if exact search term occurs in title or description
        if search_term.lower() in self.__title.lower():
            ret_val += 10
        if search_term.lower() in self.description.lower():
            ret_val += 5

        for search_token in search_term.split():
            for title_token in self.title.split():
                if QgsStringUtils.levenshteinDistance(title_token, search_token, False) < 2:
                    ret_val += 1
        # always put custom instances first
        if self.is_custom:
            ret_val *= 100
        self.last_search_result = ret_val
        return ret_val
