from bs4 import BeautifulSoup
import requests
from sys import argv, stdout
import pathlib
import logging
from logging.handlers import RotatingFileHandler


###
#  LOGIC
###

def main():
    title = 'Level One Game Shop'
    base_url = 'https://levelonegameshop.com'
    url = '{}/search?q='.format(base_url)
    search_delimiter = '+'
    conf_json = {"item_class": "halo-item", "title_class": "product-title", "oos_class": "btn product-btn product-btn-soldOut"}

    items_file = '/app/stock_files/{}_items.txt'.format(title.lower().replace(' ', '_'))
    oos_file = '/app/stock_files/{}_oos.txt'.format(title.lower().replace(' ', '_'))

    webhook = argv[2]

    logger = setup_logging()

    item_class = conf_json.get('item_class')
    title_class = conf_json.get('title_class')
    oos_class = conf_json.get('oos_class')

    logger.debug("Attempting to read current items file.")
    curr_items = read_file(items_file)
    oos_old = read_file(oos_file)
    oos_old.sort()
    logger.debug("Successfully read current items file.")

    new_items = []
    oos_new = []

    notify = []

    search_terms = []
    for term in argv[3:]:
        search_terms.append(term)
    search_terms = ['{}'.format(search_delimiter).join(str(i).split(' ')) for i in search_terms]

    for search_query in search_terms:
        logger.debug('Attempting to search for "{}" on {}.'.format(search_query, title))
        j = 1
        x = 100
        while j <= x:
            try:
                logger.debug('\ntrying query {} / trying page: {}'.format(search_query, j))
                response_html = requests.get(url+search_query+"&page={}".format(j)).content
                response = BeautifulSoup(response_html, features='lxml')
                for i in response.find_all(attrs={"class": "product"}):
                    item = Item(i, item_class, title_class, oos_class)
                    #  if item is (out of stock) and (not double counted), then add it to out of stock items
                    if item.is_oos() and str(item.id()) not in oos_new:
                        oos_new.append(str(item.id()))

                    #  if item is (new) and (not double counted), then add it to new items
                    if str(item.id()) not in curr_items and str(item.id()) not in new_items:
                        new_items.append(str(item.id()))
                        #  if item is (in stock), then notify
                        if not item.is_oos():
                            notify.append(('new', item))
                    #  if item is (not new) and (not double counted)
                    elif str(item.id()) not in new_items:
                        #  if item is (in stock) and (was previously out of stock), then notify
                        if not item.is_oos() and str(item.id()) in oos_old:
                            notify.append(('restock', item))
                if j == 1:
                    try:
                        x = int(response.find_all(attrs={"class": "page"})[-1].find('a').contents[0].strip())
                    except:
                        break
                elif x == 100:
                    break
                j += 1
            except Exception as e:
                logger.error('Error: could not parse response correctly.')
                logger.error(e)
                x = 0
                continue

    for item in notify:
        logger.debug('Attempting to send message via webhook.')
        if item[0] == 'new':
            description = 'NEW item found: ' + item[1].get_name()
        else:
            description = 'Item RESTOCK: ' + item[1].get_name()
        discord_data = {
                            'content': '{}. Click on this to buy: {}{}'.format(description, base_url, item[1].get_link())
                        }

        try:
            print('hello')
            response = requests.post(webhook, json=discord_data, headers={'Content-Type': 'application/json'})
        except Exception as e:
            logger.error('Failed to send message via webhook.')
            logger.error('Error message received: {}'.format(e))
        else:
            if response.status_code < 300:
                logger.debug('Successfully sent message via webhook.')
            else:
                logger.error('Failed to send message via webhook.')
                logger.error('Error message received: {} - {}'.format(response.status_code, response.content))

    for item_id in new_items:
        append_to_file(items_file, item_id)

    rewrite_file(oos_file, oos_new)


###
#  UTIL
###

def setup_logging():
    path = pathlib.Path(__file__).parent.absolute()

    main_logger = logging.getLogger()
    main_logger.setLevel(logging.DEBUG)

    log_file_format = "[%(levelname)s] - %(asctime)s - %(name)s - : %(message)s in %(pathname)s:%(lineno)d"

    debug_file_handler = RotatingFileHandler('/app/logs/{}_debug.txt'.format(argv[1]), maxBytes=100000, backupCount=2)
    debug_file_handler.setLevel(logging.DEBUG)
    debug_file_handler.setFormatter(logging.Formatter(log_file_format))

    error_file_handler = RotatingFileHandler('/app/logs/{}_error.txt'.format(argv[1]), maxBytes=100000, backupCount=2)
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(logging.Formatter(log_file_format))

    main_logger.addHandler(debug_file_handler)
    main_logger.addHandler(error_file_handler)

    return main_logger


def read_file(filename):
    with open(filename, 'r+') as file:
        arr = file.readlines()
        return [x.replace('\n', '') for x in arr]


def append_to_file(filename, string):
    with open(filename, 'a+') as file:
        file.write(string + '\n')


def rewrite_file(filename, lines_list):
    with open(filename, 'w+') as file:
        for line in lines_list:
            file.write(line + '\n')


class Item:
    def __init__(self, bs_obj, item_class, title_class, oos_class):
        self.bs_obj = BeautifulSoup(str(bs_obj), 'lxml')
        self.item_class = item_class
        self.title_class = title_class
        self.oos_class = oos_class
        self.item_id = self.get_id()
        self.item_name = self.get_name()
        self.item_link = self.get_link()
        self.oos = self.get_oos()

    def get_id(self):
        return self.bs_obj.find(attrs={"class": self.item_class}).find('a').contents[0].strip().replace(' ', '-').lower()

    def get_name(self):
        return self.bs_obj.find(attrs={"class": self.item_class}).find('a').contents[0].strip()

    def get_link(self):
        return str(self.bs_obj.find(attrs={"class": self.item_class}).find('a').get('href')).split('?')[0]

    def get_oos(self):
        if self.bs_obj.find(attrs={"class": self.oos_class}):
            return True
        return False

    def id(self):
        return self.item_id

    def name(self):
        return self.item_name

    def link(self):
        return self.item_link

    def is_oos(self):
        return self.oos

    def __repr__(self):
        return "{}: {} found at URL {} is {}OOS".format(self.item_id, self.item_name,
                                                        self.item_link, 'not ' if not self.oos else '')


###
# START
###

if __name__ == '__main__':
    main()
