from uuid import uuid4

from selenium import webdriver

from webdriver_manager.chrome import ChromeDriverManager

from lxml import etree, html


def save_screenshot(driver: webdriver.Chrome, path: str = '/tmp/screenshot.png') -> tuple:
    # Ref: https://stackoverflow.com/a/52572919/
    required_width = 1280
    required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
    driver.set_window_size(required_width, required_height)
    required_height = driver.execute_script('return document.body.parentNode.scrollHeight')
    driver.set_window_size(required_width, required_height)
    # driver.save_screenshot(path)  # has scrollbar
    driver.find_element_by_tag_name('body').screenshot(path)  # avoids scrollbar
    # driver.set_window_size(original_size['width'], original_size['height'])
    return required_width, required_height


def bot_bypass_for_new_page(driver):
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
    driver.execute_script("""window.navigator.chrome = {
                              app: {
                                isInstalled: false,
                              },
                              webstore: {
                                onInstallStageChanged: {},
                                onDownloadProgress: {},
                              },
                              runtime: {
                                PlatformOs: {
                                  MAC: 'mac',
                                  WIN: 'win',
                                  ANDROID: 'android',
                                  CROS: 'cros',
                                  LINUX: 'linux',
                                  OPENBSD: 'openbsd',
                                },
                                PlatformArch: {
                                  ARM: 'arm',
                                  X86_32: 'x86-32',
                                  X86_64: 'x86-64',
                                },
                                PlatformNaclArch: {
                                  ARM: 'arm',
                                  X86_32: 'x86-32',
                                  X86_64: 'x86-64',
                                },
                                RequestUpdateCheckStatus: {
                                  THROTTLED: 'throttled',
                                  NO_UPDATE: 'no_update',
                                  UPDATE_AVAILABLE: 'update_available',
                                },
                                OnInstalledReason: {
                                  INSTALL: 'install',
                                  UPDATE: 'update',
                                  CHROME_UPDATE: 'chrome_update',
                                  SHARED_MODULE_UPDATE: 'shared_module_update',
                                },
                                OnRestartRequiredReason: {
                                  APP_UPDATE: 'app_update',
                                  OS_UPDATE: 'os_update',
                                  PERIODIC: 'periodic',
                                },
                              },
                            }""")
    driver.execute_script("""const originalQuery = window.navigator.permissions.query;
                          return window.navigator.permissions.query = (parameters) => (
                          parameters.name === 'notifications' ?
                          Promise.resolve({ state: Notification.permission }) :
                          originalQuery(parameters)
                          );""")
    driver.execute_script("""Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5],
                            });""")
    driver.execute_script("""Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en'],
                          });""")


def get_screenshot(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--headless")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)

    driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.53 Safari/537.36'})
    bot_bypass_for_new_page(driver)
    driver.get(url)
    driver.implicitly_wait(5)
    file_name = str(uuid4())
    width, height = save_screenshot(driver, './{}.png'.format(file_name))
    return driver, (height, width), file_name


def get_elements(driver, dimensions, file_name):
    height = dimensions[0]
    width = dimensions[1]
    response = driver.page_source

    root = html.document_fromstring(response)
    tree = etree.ElementTree(root)
    print(etree)

    arr = []

    for elem in root.iter(tag=etree.Element):
        try:
            path = tree.getpath(elem)
            split_path = path.split('/')
            last_tag = split_path[-1].split('[')[0]
            invalid_tags = ['comment()', 'script', 'style', 'body', 'dom-module']
            if (len(split_path) >= 3 and 'head' not in split_path[2]) and \
                    'svg' not in path and 'noscript' not in path and last_tag not in invalid_tags:

                node = driver.execute_script("""let node = document.evaluate('{}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;  
                                               let ret = {{}}; ret['bounds'] = node.getBoundingClientRect();  ret['class'] = node.className; ret['text'] = node.innerText;
                                               ret['link'] = node.href; return ret;
                                               """.format(path))
                if int(node['bounds']['y']) < 0 or int(node['bounds']['x']) < 0 or \
                        int(node['bounds']['height']) * int(node['bounds']['width']) <= 1 or \
                        int(node['bounds']['height']) + int(node['bounds']['y']) > height or \
                        int(node['bounds']['width']) + int(node['bounds']['x']) > width\
                        or not node['class']:
                    continue

                arr.append({
                    'x': node['bounds']['x'],
                    'y': node['bounds']['y'],
                    'width': node['bounds']['width'],
                    'height': node['bounds']['height'],
                    'z-index': len(split_path),
                    'xpath': path,
                    'class': node['class'],
                    'text': node['text'].replace('"', '').replace("'", '') if node['text'] else "",
                    'link': node['link'].replace('"', '').replace("'", '') if node['link'] else ""
                })
        except Exception as e:
            print(e)

    driver.close()
    driver.quit()

    with open('./{}.json'.format(file_name), 'w+') as file:
        file.write("{}".format(arr).replace("'", '"').replace("\\", '\\\\'))
